"""Project persistence: save/open self-contained project folders on disk.

A project is a portable folder::

    <project>/
        project.json          # manifest (metadata + per-cell organisational info)
        data/
            c1.cellpy         # each cell saved as a self-contained cellpy file
            c2.cellpy

Saving writes every loaded cell to its own ``.cellpy`` file, so a project is
fully self-contained and can be zipped/moved. Opening reloads those files and
restores the user's grouping / labels / selection from the manifest.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Callable, Literal, Optional

from pydantic import BaseModel, Field

from .. import __version__ as APP_VERSION
from ..config import get_settings
from . import cellpy_adapter as adapter
from .library import Library

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ProgressFn = Optional[Callable[[float, str], None]]


# --------------------------------------------------------------------------- #
# Manifest models
# --------------------------------------------------------------------------- #


class CellEntry(BaseModel):
    id: str
    name: str
    source: str
    data_file: str  # relative to the project folder, e.g. "data/c1.cellpy"
    group: int = 1
    label: str = ""
    selected: bool = True
    mass: float | None = None
    area: float | None = None
    nominal_capacity: float | None = None
    n_cycles: int = 0


class ProjectManifest(BaseModel):
    schema_version: int = SCHEMA_VERSION
    name: str
    slug: str
    created: str
    modified: str
    cellpy_version: str = ""
    app_version: str = APP_VERSION
    cells: list[CellEntry] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    name: str
    slug: str
    path: str
    n_cells: int
    modified: str


# --------------------------------------------------------------------------- #
# Paths / helpers
# --------------------------------------------------------------------------- #


def projects_root() -> Path:
    root = get_settings().data_dir / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name.strip().lower()).strip("_")
    return slug or "project"


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_project_path(path_or_slug: str) -> Path:
    """Accept a project folder, ``project.json`` file, or known slug/name."""
    p = Path(path_or_slug)
    if p.is_file() and p.name == "project.json":
        p = p.parent
    if p.is_dir() and (p / "project.json").exists():
        return p
    cand = projects_root() / slugify(path_or_slug)
    if (cand / "project.json").exists():
        return cand
    raise FileNotFoundError(f"No project found for {path_or_slug!r}")


def classify_import_path(path: str) -> Literal["project", "journal"]:
    """Decide whether ``path`` is a portable app project or a batch journal.

    Rules (filename / directory only — no JSON sniffing):

    - Directory containing ``project.json`` → ``"project"``
    - File named ``project.json`` → ``"project"``
    - Any other existing file → ``"journal"`` (cellpy validates)
    """
    raw = (path or "").strip()
    if not raw:
        raise ValueError("A project folder, project.json, or journal path is required.")
    p = Path(raw)
    if p.is_dir() and (p / "project.json").is_file():
        return "project"
    if p.is_file() and p.name == "project.json":
        return "project"
    if p.is_file():
        return "journal"
    if p.is_dir():
        raise ValueError(
            f"Folder is not a portable project (missing project.json): {p}"
        )
    raise ValueError(f"Path not found: {p}")


# --------------------------------------------------------------------------- #
# Save / open / list
# --------------------------------------------------------------------------- #


def save_project(library: Library, name: str, progress: ProgressFn = None) -> ProjectManifest:
    records = library.all()
    if not records:
        raise ValueError("Nothing to save — load some cells first.")

    slug = slugify(name)
    pdir = projects_root() / slug
    data_dir = pdir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # preserve original creation time if re-saving
    created = _now()
    existing = pdir / "project.json"
    if existing.exists():
        try:
            created = ProjectManifest(**json.loads(existing.read_text())).created
        except Exception:  # noqa: BLE001
            pass

    # clear stale .cellpy files (cells removed since last save)
    for old in data_dir.glob("*.cellpy"):
        old.unlink(missing_ok=True)

    total = len(records)
    entries: list[CellEntry] = []
    for i, rec in enumerate(records):
        if progress:
            progress(i / total, f"Saving “{rec.label or rec.name}” …")
        data_file = f"{rec.id}.cellpy"
        adapter.save_cell(rec.cell, data_dir / data_file)
        entries.append(
            CellEntry(
                id=rec.id, name=rec.name, source=rec.source,
                data_file=f"data/{data_file}",
                group=rec.group, label=rec.label, selected=rec.selected,
                mass=rec.mass, area=rec.area,
                nominal_capacity=rec.nominal_capacity, n_cycles=rec.n_cycles,
            )
        )

    manifest = ProjectManifest(
        name=name, slug=slug, created=created, modified=_now(),
        cellpy_version=_safe_cellpy_version(), cells=entries,
    )
    (pdir / "project.json").write_text(json.dumps(manifest.model_dump(), indent=2))

    library.project_name = name
    library.project_path = str(pdir)
    if progress:
        progress(1.0, "Saved")
    return manifest


def open_project(library: Library, path_or_slug: str, progress: ProgressFn = None) -> ProjectManifest:
    pdir = resolve_project_path(path_or_slug)
    manifest = ProjectManifest(**json.loads((pdir / "project.json").read_text()))

    library.clear()
    total = max(len(manifest.cells), 1)
    log.info("Opening project “%s” (%d cell(s)) from %s", manifest.name, len(manifest.cells), pdir)
    for i, entry in enumerate(manifest.cells):
        label = entry.label or entry.name
        data_path = pdir / entry.data_file
        log.info("Project open: loading %d/%d “%s” ← %s", i + 1, total, label, data_path)
        if progress:
            progress(i / total, f"Loading “{label}” ({i + 1}/{total}) …")
        cell = adapter.load_file(data_path)
        library.restore_cell(
            cell, source=entry.source, group=entry.group,
            label=entry.label, selected=entry.selected,
        )
        log.info("Project open: loaded %d/%d “%s”", i + 1, total, label)

    library.project_name = manifest.name
    library.project_path = str(pdir)
    if progress:
        progress(1.0, "Opened")
    log.info("Opened project “%s” (%d cell(s))", manifest.name, len(manifest.cells))
    return manifest


def list_projects() -> list[ProjectSummary]:
    out: list[ProjectSummary] = []
    for child in sorted(projects_root().iterdir()):
        manifest_file = child / "project.json"
        if not manifest_file.is_file():
            continue
        try:
            m = ProjectManifest(**json.loads(manifest_file.read_text()))
        except Exception:  # noqa: BLE001
            continue
        out.append(
            ProjectSummary(
                name=m.name, slug=m.slug, path=str(child),
                n_cells=len(m.cells), modified=m.modified,
            )
        )
    out.sort(key=lambda s: s.modified, reverse=True)
    return out


def delete_project(slug: str) -> None:
    pdir = projects_root() / slugify(slug)
    if (pdir / "project.json").exists():
        shutil.rmtree(pdir, ignore_errors=True)


def _safe_cellpy_version() -> str:
    try:
        return adapter.cellpy_version()
    except Exception:  # noqa: BLE001
        return ""
