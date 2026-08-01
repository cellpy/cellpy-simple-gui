"""In-memory library of loaded cells — the backend's source of truth.

For a single-user desktop app this is deliberately simple: one process-wide
``Library`` holding ``CellRecord`` objects. The UI never holds cell state; it
always reads from here, so a browser refresh or reconnect never loses work.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import cellpy_adapter as adapter
from .models import CellMeta

# A colour-blind-friendly qualitative palette (Plotly "Safe"-ish), used to
# colour cells/groups consistently across every plot.
PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]


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

    def color(self) -> str:
        return PALETTE[(self.group - 1) % len(PALETTE)]

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
        self._counter = itertools.count(1)
        self._lock = threading.RLock()
        # Current on-disk project this library is associated with (if any).
        self.project_name: str | None = None
        self.project_path: str | None = None

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
            return record

    def restore_cell(
        self,
        cell: Any,
        *,
        source: str = "project",
        group: int = 1,
        label: str = "",
        selected: bool = True,
    ) -> CellRecord:
        """Add a cell while preserving saved organisational metadata.

        Physical quantities (mass/area/nominal capacity/basis/cycle mode/cycles)
        are read fresh from the ``.cellpy`` file — it is the source of truth for
        those — while group/label/selection come from the project manifest.
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
            return record

    def remove(self, rid: str) -> None:
        with self._lock:
            self._records.pop(rid, None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self.project_name = None
            self.project_path = None

    def set_selection(self, selected: bool) -> None:
        with self._lock:
            for r in self._records.values():
                r.selected = selected

    # -- access ----------------------------------------------------------- #
    def get(self, rid: str) -> CellRecord:
        with self._lock:
            return self._records[rid]

    def all(self) -> list[CellRecord]:
        with self._lock:
            return list(self._records.values())

    def selected(self) -> list[CellRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.selected]

    def __len__(self) -> int:
        return len(self._records)

    def is_empty(self) -> bool:
        return len(self._records) == 0

    def metas(self) -> list[CellMeta]:
        return [r.to_meta() for r in self.all()]

    def n_groups(self) -> int:
        return len({r.group for r in self.all()})


_LIBRARY: Library | None = None


def get_library() -> Library:
    """Return the process-wide library singleton."""
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = Library()
    return _LIBRARY
