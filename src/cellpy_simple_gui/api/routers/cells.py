"""Endpoints for loading cells and editing the journal (library)."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from ...core import cellpy_adapter
from ...core.library import get_library
from ...core.models import (
    JournalRowUpdate,
    LoadExampleRequest,
    LoadFilesRequest,
)
from ..jobs import Progress, get_job_manager

log = logging.getLogger(__name__)
router = APIRouter()


def _state() -> dict:
    lib = get_library()
    return {
        "cells": [m.model_dump() for m in lib.metas()],
        "n_cells": len(lib),
        "n_selected": len(lib.selected()),
        "n_groups": lib.n_groups(),
        "empty": lib.is_empty(),
        "project": lib.project_name,
    }


@router.get("/examples")
def list_examples() -> list[dict]:
    return [
        {"id": key, "label": val["label"], "description": val["description"]}
        for key, val in cellpy_adapter.EXAMPLE_CELLS.items()
    ]


@router.get("/state")
def get_state() -> dict:
    return _state()


# --------------------------- loading (as jobs) ----------------------------- #


def _load_examples_job(progress: Progress, kinds: list[str]) -> dict:
    lib = get_library()
    added, errors = [], []
    total = len(kinds)
    for i, kind in enumerate(kinds):
        progress.update(i / max(total, 1), f"Loading example “{kind}” …")
        try:
            cell = cellpy_adapter.load_example(kind)
            rec = lib.add_cell(cell, source=f"example:{kind}")
            added.append(rec.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{kind}: {exc}")
        progress.update((i + 1) / max(total, 1))
    time.sleep(0.15)
    return {"added": added, "errors": errors}


def _load_files_job(progress: Progress, paths: list[str], max_files: int) -> dict:
    from ...core.files import expand_paths

    lib = get_library()
    exp = expand_paths(paths, max_files=max_files)
    added, errors = [], list(exp.errors)
    total = len(exp.paths)
    for i, path in enumerate(exp.paths):
        progress.update(i / max(total, 1), f"Loading {path} …")
        try:
            cell = cellpy_adapter.load_file(path)
            rec = lib.add_cell(cell, source="file")
            added.append(rec.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
        progress.update((i + 1) / max(total, 1))
    return {"added": added, "errors": errors, "notes": exp.notes}


@router.post("/load/example")
def load_example(req: LoadExampleRequest) -> dict:
    log.info("Load demo cells: %s", ", ".join(req.kinds) or "(none)")
    job = get_job_manager().submit("load-example", _load_examples_job, req.kinds)
    return {"job_id": job.id}


@router.post("/load/files")
def load_files(req: LoadFilesRequest) -> dict:
    if not req.paths:
        raise HTTPException(400, "No paths provided")
    log.info("Load cellpy files: %d path(s)", len(req.paths))
    job = get_job_manager().submit("load-files", _load_files_job, req.paths, req.max_files)
    return {"job_id": job.id}


# ------------------------------ editing ------------------------------------ #


@router.post("/cells/{cell_id}/update")
def update_cell(cell_id: str, update: JournalRowUpdate) -> dict:
    lib = get_library()
    try:
        rec = lib.update(
            cell_id,
            group=update.group,
            label=update.label,
            selected=update.selected,
            mass=update.mass,
            area=update.area,
            nominal_capacity=update.nominal_capacity,
            nom_cap_specifics=update.nom_cap_specifics,
            cycle_mode=update.cycle_mode,
        )
    except KeyError:
        raise HTTPException(404, "No such cell")
    return {"cell": rec.to_meta().model_dump(), "state": _state()}


@router.post("/cells/select")
def select_all(value: bool = True) -> dict:
    get_library().set_selection(value)
    return _state()


@router.delete("/cells/{cell_id}")
def delete_cell(cell_id: str) -> dict:
    get_library().remove(cell_id)
    return _state()


@router.post("/cells/clear")
def clear() -> dict:
    n = len(get_library())
    get_library().clear()
    log.info("Cleared library (%d cell(s))", n)
    return _state()
