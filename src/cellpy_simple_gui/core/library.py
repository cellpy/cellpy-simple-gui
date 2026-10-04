"""In-memory library of loaded cells — the backend's source of truth.

For a single-user desktop app this is deliberately simple: one process-wide
``Library`` holding ``CellRecord`` objects. The UI never holds cell state; it
always reads from here, so a browser refresh or reconnect never loses work.
"""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import cellpy_adapter as adapter
from .models import CellMeta

# A colour-blind-friendly qualitative palette (Plotly "Safe"-ish), used to
# colour cells/groups consistently across every plot.
PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]

log = logging.getLogger(__name__)


def default_group_label(group: int) -> str:
    """The name a group has until the user gives it one (cellpy's default too)."""
    return f"group {int(group)}"


def file_stat(path: str | Path) -> tuple[int, int] | None:
    """``(size, mtime_ns)`` for ``path``, or ``None`` if it cannot be read.

    Cheap identity for "is this still the file we read?" — enough to notice a
    file rewritten behind the app's back, without hashing megabytes on save.
    """
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


@dataclass
class CellRecord:
    """A loaded cell plus its mutable, user-editable metadata."""

    id: str
    cell: Any  # cellpy CellpyCell (opaque outside the adapter)
    name: str
    source: str = "example"
    mass: float | None = None
    area: float | None = None
    nominal_capacity: float | None = None
    nom_cap_specifics: str | None = None
    cycle_mode: str | None = None
    n_cycles: int = 0
    group: int = 1
    label: str = ""
    selected: bool = True

    #: Where this record's data was read from, when that file is known to be a
    #: faithful representation of ``cell`` — set on project open, cleared the
    #: moment anything mutates the cell. Lets Save skip re-serialising a cell
    #: whose data has not changed (#29).
    data_path: str | None = None
    #: ``(size, mtime_ns)`` of ``data_path`` when it was read, so a file edited
    #: behind the app's back is not mistaken for one we still match.
    data_stat: tuple[int, int] | None = None
    #: True until we can prove otherwise. New cells have no on-disk copy in the
    #: project yet, so the default is the safe one: write it.
    data_dirty: bool = True
    #: User-given name of this record's group (#187). Group names are a
    #: library-level thing; the library stamps this snapshot onto every record
    #: it hands out so collectors see it without extra plumbing. Empty means
    #: "unnamed" — :func:`default_group_label` applies.
    group_label: str = ""
    #: Copy of ``Library.revision`` after the last touch. Plot-cache keys
    #: include it so a data edit misses without hashing the cell frame.
    cache_revision: int = 0

    def color(self) -> str:
        return PALETTE[(self.group - 1) % len(PALETTE)]

    def group_name(self) -> str:
        """The group's display name: the custom label, else ``group <n>``."""
        return self.group_label or default_group_label(self.group)

    def to_meta(self) -> CellMeta:
        return CellMeta(
            id=self.id,
            name=self.name,
            source=self.source,
            mass=self.mass,
            area=self.area,
            nominal_capacity=self.nominal_capacity,
            nom_cap_specifics=self.nom_cap_specifics,  # type: ignore[arg-type]
            cycle_mode=self.cycle_mode,  # type: ignore[arg-type]
            n_cycles=self.n_cycles,
            group=self.group,
            group_label=self.group_name(),
            label=self.label or self.name,
            selected=self.selected,
            color=self.color(),
        )

    def _apply_physical_meta(self, meta: dict) -> None:
        self.mass = meta["mass"]
        self.area = meta["area"]
        self.nominal_capacity = meta["nominal_capacity"]
        self.nom_cap_specifics = meta.get("nom_cap_specifics")
        self.cycle_mode = meta.get("cycle_mode")
        if "n_cycles" in meta:
            self.n_cycles = int(meta["n_cycles"] or 0)


class Library:
    """Thread-safe ordered collection of :class:`CellRecord`."""

    def __init__(self) -> None:
        self._records: dict[str, CellRecord] = {}
        # Custom group names by group number (#187). Only names the user (or a
        # journal / manifest) set are stored; unnamed groups fall back to
        # ``default_group_label``.
        self._group_labels: dict[int, str] = {}
        self._counter = itertools.count(1)
        self._lock = threading.RLock()
        # Current on-disk project this library is associated with (if any).
        self.project_name: str | None = None
        self.project_path: str | None = None
        # Bumped by every mutator that can change a plot. ``mark_saved`` does
        # not. Plot cache keys and ``/api/state`` both read this.
        self.revision: int = 0

    def _touch(self) -> None:
        """Invalidate plot caches and stamp every record with the new revision.

        Call this from a mutator, inside the library lock. The names that must
        call it are ``plot_cache.BUMPS``.
        """
        from . import plot_cache

        self.revision += 1
        for record in self._records.values():
            record.cache_revision = self.revision
        plot_cache.invalidate()

    # -- mutation --------------------------------------------------------- #
    def add_cell(self, cell: Any, *, source: str = "example") -> CellRecord:
        meta = adapter.read_meta(cell)
        with self._lock:
            n = next(self._counter)
            rid = f"c{n}"
            record = CellRecord(
                id=rid,
                cell=cell,
                name=meta["name"] or rid,
                source=source,
                mass=meta["mass"],
                area=meta["area"],
                nominal_capacity=meta["nominal_capacity"],
                nom_cap_specifics=meta.get("nom_cap_specifics"),
                cycle_mode=meta.get("cycle_mode"),
                n_cycles=meta["n_cycles"],
                group=n,  # each new cell starts in its own group
                label=meta["name"] or rid,
                selected=True,
            )
            self._records[rid] = record
            self._touch()
            return record

    def restore_cell(
        self,
        cell: Any,
        *,
        source: str = "project",
        group: int = 1,
        label: str = "",
        selected: bool = True,
        data_path: str | Path | None = None,
    ) -> CellRecord:
        """Add a cell while preserving saved organisational metadata.

        Physical quantities (mass/area/nominal capacity/basis/cycle mode/cycles)
        are read fresh from the ``.cellpy`` file — it is the source of truth for
        those — while group/label/selection come from the project manifest.

        ``data_path`` records the file this cell came from. It is only passed
        for project data, which this app wrote itself, so the format is known
        current — a loose ``.h5`` would be a legacy file and copying it into a
        project as ``.cellpy`` would quietly downgrade the project (#29).
        """
        meta = adapter.read_meta(cell)
        with self._lock:
            n = next(self._counter)
            rid = f"c{n}"
            record = CellRecord(
                id=rid,
                cell=cell,
                name=meta["name"] or rid,
                source=source,
                mass=meta["mass"],
                area=meta["area"],
                nominal_capacity=meta["nominal_capacity"],
                nom_cap_specifics=meta.get("nom_cap_specifics"),
                cycle_mode=meta.get("cycle_mode"),
                n_cycles=meta["n_cycles"],
                group=int(group),
                label=label or meta["name"] or rid,
                selected=bool(selected),
            )
            self._records[rid] = record
            if data_path is not None:
                self._mark_clean(record, data_path)
            self._touch()
            return record

    def update(
        self,
        rid: str,
        *,
        group: int | None = None,
        label: str | None = None,
        selected: bool | None = None,
        mass: float | None = None,
        area: float | None = None,
        nominal_capacity: float | None = None,
        nom_cap_specifics: str | None = None,
        cycle_mode: str | None = None,
    ) -> CellRecord:
        with self._lock:
            record = self._records[rid]
            if group is not None:
                record.group = int(group)
            if label is not None:
                record.label = label
            if selected is not None:
                record.selected = bool(selected)
            changed = adapter.apply_physical_meta(
                record.cell,
                mass=mass,
                area=area,
                nominal_capacity=nominal_capacity,
                nom_cap_specifics=nom_cap_specifics,
                cycle_mode=cycle_mode,
            )
            if changed:
                record._apply_physical_meta(adapter.read_meta(record.cell))
                # The cell itself moved — mass/area/nom-cap/cycle-mode all
                # rewrite the summary — so the file on disk no longer matches.
                # group/label/selection live in the manifest and do not.
                record.data_dirty = True
                record.data_path = None
                record.data_stat = None
            self._touch()
            return record

    # -- save provenance (#29) -------------------------------------------- #
    def _mark_clean(self, record: CellRecord, path: str | Path) -> None:
        record.data_path = str(Path(path).resolve())
        record.data_stat = file_stat(path)
        # A file we cannot stat is a file we cannot vouch for.
        record.data_dirty = record.data_stat is None

    def mark_saved(self, rid: str, path: str | Path) -> None:
        """Record that ``rid``'s data was just written to ``path``."""
        with self._lock:
            record = self._records.get(rid)
            if record is not None:
                self._mark_clean(record, path)

    def reusable_data_file(self, rid: str) -> Path | None:
        """The on-disk copy of ``rid``'s data, when it provably still matches.

        Three things must hold, and any doubt means "no": the cell has not been
        mutated since it was read, the file is still there, and it has not
        changed since we read it.
        """
        with self._lock:
            record = self._records.get(rid)
        if record is None or record.data_dirty or not record.data_path:
            return None
        path = Path(record.data_path)
        if not path.is_file():
            return None
        if file_stat(path) != record.data_stat:
            log.info("%s changed on disk since it was read — rewriting", path)
            return None
        return path

    def remove(self, rid: str) -> None:
        with self._lock:
            self._records.pop(rid, None)
            self._touch()

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._group_labels.clear()
            self.project_name = None
            self.project_path = None
            self._touch()

    def set_selection(self, selected: bool) -> None:
        with self._lock:
            for r in self._records.values():
                r.selected = selected
            self._touch()

    # -- group names (#187) ----------------------------------------------- #
    def set_group_label(self, group: int, label: str | None) -> None:
        """Name ``group``; an empty / whitespace label restores the default."""
        g = int(group)
        text = (label or "").strip()
        with self._lock:
            if text and text != default_group_label(g):
                self._group_labels[g] = text
            else:
                self._group_labels.pop(g, None)
            self._touch()

    def group_label(self, group: int) -> str:
        """The custom name of ``group`` (empty when it has none)."""
        with self._lock:
            return self._group_labels.get(int(group), "")

    def group_labels(self) -> dict[int, str]:
        """Custom names of the groups that currently hold cells."""
        with self._lock:
            in_use = {r.group for r in self._records.values()}
            return {g: lbl for g, lbl in self._group_labels.items() if g in in_use}

    def groups(self) -> list[dict]:
        """One row per group in use: id, custom label, display name, size, colour."""
        with self._lock:
            counts: dict[int, int] = {}
            for r in self._records.values():
                counts[r.group] = counts.get(r.group, 0) + 1
            return [
                {
                    "id": g,
                    "label": self._group_labels.get(g, ""),
                    "name": self._group_labels.get(g) or default_group_label(g),
                    "n_cells": n,
                    "color": PALETTE[(g - 1) % len(PALETTE)],
                }
                for g, n in sorted(counts.items())
            ]

    # -- access ----------------------------------------------------------- #
    def get(self, rid: str) -> CellRecord:
        with self._lock:
            return self._records[rid]

    def all(self) -> list[CellRecord]:
        with self._lock:
            records = list(self._records.values())
            for r in records:
                r.group_label = self._group_labels.get(r.group, "")
            return records

    def selected(self) -> list[CellRecord]:
        return [r for r in self.all() if r.selected]

    def __len__(self) -> int:
        return len(self._records)

    def is_empty(self) -> bool:
        return len(self._records) == 0

    def metas(self) -> list[CellMeta]:
        return [r.to_meta() for r in self.all()]

    def n_groups(self) -> int:
        return len({r.group for r in self.all()})

    def group_offset_for_append(self) -> int:
        """Add this to incoming group numbers so they land above every group in use.

        Appending a project or journal keeps its internal grouping (1, 2, …
        become offset+1, offset+2, …) without colliding with the groups already
        loaded (#174). Zero when the library is empty.
        """
        with self._lock:
            return max((r.group for r in self._records.values()), default=0)


_LIBRARY: Library | None = None


def get_library() -> Library:
    """Return the process-wide library singleton."""
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = Library()
    return _LIBRARY
