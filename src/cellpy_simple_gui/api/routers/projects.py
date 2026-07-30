"""Project persistence endpoints (save/open/list) — save & open run as jobs."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from ...core import cellpy_adapter, projects
from ...core.library import get_library
from ..jobs import Progress, get_job_manager

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/projects")
def list_projects() -> dict:
    lib = get_library()
    return {
        "projects": [p.model_dump() for p in projects.list_projects()],
        "current": {"name": lib.project_name, "path": lib.project_path},
    }


def _save_job(progress: Progress, name: str) -> dict:
    manifest = projects.save_project(
        get_library(), name, progress=lambda f, m: progress.update(f, m)
    )
    return {
        "action": "saved",
        "name": manifest.name,
        "slug": manifest.slug,
        "n_cells": len(manifest.cells),
    }


def _open_job(progress: Progress, target: str) -> dict:
    manifest = projects.open_project(
        get_library(), target, progress=lambda f, m: progress.update(f, m)
    )
    return {
        "action": "opened",
        "name": manifest.name,
        "slug": manifest.slug,
        "n_cells": len(manifest.cells),
    }


@router.post("/projects/save")
def save_project(name: str = Body(..., embed=True)) -> dict:
    if not name.strip():
        raise HTTPException(400, "A project name is required.")
    if get_library().is_empty():
        raise HTTPException(400, "Nothing to save — load some cells first.")
    log.info("Saving project “%s” (%d cell(s))", name.strip(), len(get_library()))
    job = get_job_manager().submit("save-project", _save_job, name.strip())
    return {"job_id": job.id}


@router.post("/projects/open")
def open_project(target: str = Body(..., embed=True)) -> dict:
    try:
        projects.resolve_project_path(target)
    except FileNotFoundError:
        raise HTTPException(404, f"No project found for “{target}”.")
    log.info("Opening project “%s”", target)
    job = get_job_manager().submit("open-project", _open_job, target)
    return {"job_id": job.id}


def _load_journal_job(progress: Progress, path: str) -> dict:
    """Always return a toastable result — never leave the UI waiting on a bare raise."""
    from ..jobs import Cancelled

    lib = get_library()
    progress.update(0.05, f"Reading journal {Path(path).name} …")
    progress.check_cancel()
    try:
        # Long cellpy call — cancel cannot interrupt mid-call; UI has Dismiss.
        triples = cellpy_adapter.load_journal_cells(path)
    except Exception as exc:  # noqa: BLE001 - surface to the user via job result
        return {"added": [], "errors": [f"Failed to load journal: {exc}"]}
    progress.check_cancel()
    if not triples:
        return {"added": [], "errors": [
            "No cells could be linked from that journal "
            "(are the referenced .cellpy files present?)."
        ]}
    added, errors = [], []
    total = len(triples)
    for i, (label, cell, group) in enumerate(triples):
        try:
            progress.update(i / total, f"Loading “{label}” …")
        except Cancelled:
            log.info("Journal load cancelled after %d cell(s)", len(added))
            raise
        try:
            rec = lib.restore_cell(cell, source="journal", group=group, label=label, selected=True)
            added.append(rec.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {exc}")
    return {"added": added, "errors": errors}


@router.post("/projects/load-journal")
def load_journal(path: str = Body(..., embed=True)) -> dict:
    if not path.strip():
        raise HTTPException(400, "A journal file path is required.")
    if not Path(path).is_file():
        raise HTTPException(404, f"No such file: {path}")
    log.info("Loading journal %s", path.strip())
    job = get_job_manager().submit("load-journal", _load_journal_job, path.strip())
    return {"job_id": job.id}


@router.delete("/projects/{slug}")
def delete_project(slug: str) -> dict:
    log.info("Deleting project slug=%s", slug)
    projects.delete_project(slug)
    lib = get_library()
    # If we just deleted the project the library is associated with, drop the
    # stale link (the loaded cells stay in memory).
    if lib.project_name and projects.slugify(lib.project_name) == projects.slugify(slug):
        lib.project_name = None
        lib.project_path = None
    return {
        "projects": [p.model_dump() for p in projects.list_projects()],
        "current": {"name": lib.project_name, "path": lib.project_path},
    }
