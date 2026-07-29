"""Project persistence endpoints (save/open/list) — save & open run as jobs."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from ...core import projects
from ...core.library import get_library
from ..jobs import Progress, get_job_manager

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
    return {"name": manifest.name, "slug": manifest.slug, "n_cells": len(manifest.cells)}


def _open_job(progress: Progress, target: str) -> dict:
    manifest = projects.open_project(
        get_library(), target, progress=lambda f, m: progress.update(f, m)
    )
    return {"name": manifest.name, "slug": manifest.slug, "n_cells": len(manifest.cells)}


@router.post("/projects/save")
def save_project(name: str = Body(..., embed=True)) -> dict:
    if not name.strip():
        raise HTTPException(400, "A project name is required.")
    if get_library().is_empty():
        raise HTTPException(400, "Nothing to save — load some cells first.")
    job = get_job_manager().submit("save-project", _save_job, name.strip())
    return {"job_id": job.id}


@router.post("/projects/open")
def open_project(target: str = Body(..., embed=True)) -> dict:
    try:
        projects.resolve_project_path(target)
    except FileNotFoundError:
        raise HTTPException(404, f"No project found for “{target}”.")
    job = get_job_manager().submit("open-project", _open_job, target)
    return {"job_id": job.id}


@router.delete("/projects/{slug}")
def delete_project(slug: str) -> dict:
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
