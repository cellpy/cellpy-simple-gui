"""Project persistence endpoints (save/open/list) — save & open run as jobs."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from ...core import cellpy_adapter, cellpy_config, projects
from ...core.library import get_library
from ..jobs import Progress, get_job_manager

log = logging.getLogger(__name__)
router = APIRouter()


def _current_state(lib) -> dict:
    """Current project + whether it brought its own cellpy settings."""
    active = cellpy_config.active_project_config()
    return {
        "name": lib.project_name,
        "path": lib.project_path,
        "cellpy_config": str(active) if active else None,
    }


@router.get("/projects")
def list_projects() -> dict:
    lib = get_library()
    return {
        "projects": [p.model_dump() for p in projects.list_projects()],
        "current": _current_state(lib),
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
        pdir = projects.resolve_project_path(target)
    except FileNotFoundError:
        raise HTTPException(404, f"No project found for “{target}”.")
    log.info("Opening project “%s”", target)
    # Switch cellpy's config here, on the request thread and *before* the load
    # job starts: the cells must be read under this project's settings, and the
    # config session is process-global and not thread-safe (cellpy #850).
    project_config = cellpy_config.activate_project_config(pdir)
    job = get_job_manager().submit("open-project", _open_job, target)
    return {
        "job_id": job.id,
        "project_config": str(project_config) if project_config else None,
    }


@router.post("/projects/pin-config")
def pin_config() -> dict:
    """Write the current cellpy settings into the open project and activate them."""
    lib = get_library()
    if not lib.project_path:
        raise HTTPException(
            400, "Save or open a project first — settings are pinned to a project folder."
        )
    try:
        path = cellpy_config.pin_project_config(lib.project_path)
    except Exception as exc:  # noqa: BLE001 - surface the reason to the user
        log.error("Pinning cellpy settings failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Could not pin settings: {exc}") from exc
    log.info("Pinned cellpy settings to project “%s”", lib.project_name)
    return {
        "path": str(path),
        "sections": list(cellpy_config.PINNED_SECTIONS),
        "current": _current_state(lib),
    }


@router.post("/projects/classify-import")
def classify_import(path: str = Body(..., embed=True)) -> dict:
    """Return whether a path is a portable project or a batch journal (#75)."""
    try:
        kind = projects.classify_import_path(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"kind": kind, "path": path.strip()}


def _load_journal_job(progress: Progress, path: str) -> dict:
    """Always return a toastable result — never leave the UI waiting on a bare raise."""
    from ..jobs import Cancelled

    lib = get_library()
    name = Path(path).name
    log.info("Journal job: start “%s”", name)
    progress.check_cancel()
    try:
        # Long cellpy call — cancel cannot interrupt mid-cell; UI has Dismiss.
        # Adapter reports from_journal / per-cell batch.load progress + logs.
        triples = cellpy_adapter.load_journal_cells(
            path,
            progress=lambda f, m: progress.update(f, m),
        )
    except Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001 - surface to the user via job result
        log.error("Journal job failed for “%s”: %s", name, exc)
        return {"added": [], "errors": [f"Failed to load journal: {exc}"]}
    progress.check_cancel()
    log.info("Journal job: cellpy returned %d linkable cell(s)", len(triples))
    if not triples:
        return {"added": [], "errors": [
            "No cells could be linked from that journal "
            "(are the referenced .cellpy files present?)."
        ]}
    added, errors = [], []
    total = len(triples)
    for i, (label, cell, group) in enumerate(triples):
        try:
            progress.update(
                0.85 + 0.15 * (i / total),
                f"Adding to library {i + 1}/{total}: “{label}” …",
            )
        except Cancelled:
            log.info("Journal load cancelled after %d cell(s)", len(added))
            raise
        try:
            rec = lib.restore_cell(cell, source="journal", group=group, label=label, selected=True)
            added.append(rec.id)
            log.info("Journal job: added %d/%d “%s” (group %s)", i + 1, total, label, group)
        except Exception as exc:  # noqa: BLE001
            log.error("Journal job: failed “%s”: %s", label, exc)
            errors.append(f"{label}: {exc}")
    log.info(
        "Journal job: done “%s” — %d added, %d error(s)",
        name,
        len(added),
        len(errors),
    )
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
        cellpy_config.deactivate_project_config()
    return {
        "projects": [p.model_dump() for p in projects.list_projects()],
        "current": _current_state(lib),
    }
