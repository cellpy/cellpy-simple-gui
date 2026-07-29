"""Raw-file ingestion: turn instrument files into cellpy cells (as jobs)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...core import cellpy_adapter
from ...core.library import get_library
from ...core.models import IngestExampleRequest, IngestRequest
from ..jobs import Progress, get_job_manager

router = APIRouter()


@router.get("/instruments")
def list_instruments() -> dict:
    return {
        "instruments": cellpy_adapter.INSTRUMENTS,
        "examples": [
            {"kind": k, "label": v["label"]} for k, v in cellpy_adapter.EXAMPLE_RAW.items()
        ],
    }


def _ingest_job(progress: Progress, req: IngestRequest) -> dict:
    lib = get_library()
    added, errors = [], []
    total = len(req.paths)
    for i, path in enumerate(req.paths):
        progress.update(i / max(total, 1), f"Processing {path} …")
        try:
            cell = cellpy_adapter.load_raw(
                path, req.instrument, model=req.model, mass=req.mass, area=req.area,
                nominal_capacity=req.nominal_capacity,
                nom_cap_specifics=req.nom_cap_specifics, cycle_mode=req.cycle_mode,
            )
            rec = lib.add_cell(cell, source=f"raw:{req.instrument}")
            added.append(rec.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
        progress.update((i + 1) / max(total, 1))
    return {"added": added, "errors": errors}


def _ingest_example_job(progress: Progress, kind: str, mass: float | None) -> dict:
    lib = get_library()
    spec = cellpy_adapter.EXAMPLE_RAW[kind]
    progress.update(0.1, f"Fetching {spec['label']} …")
    path = cellpy_adapter.example_raw_path(kind)
    progress.update(0.4, f"Processing {spec['label']} …")
    try:
        cell = cellpy_adapter.load_raw(
            path, spec["instrument"], model=spec["model"], mass=mass,
        )
        rec = lib.add_cell(cell, source=f"raw:{spec['instrument']}")
        return {"added": [rec.id], "errors": []}
    except Exception as exc:  # noqa: BLE001
        return {"added": [], "errors": [f"{spec['label']}: {exc}"]}


@router.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    if not req.paths:
        raise HTTPException(400, "No files provided.")
    valid = {i["id"] for i in cellpy_adapter.INSTRUMENTS}
    if req.instrument not in valid:
        raise HTTPException(400, f"Unknown instrument: {req.instrument}")
    job = get_job_manager().submit("ingest", _ingest_job, req)
    return {"job_id": job.id}


@router.post("/ingest/example")
def ingest_example(req: IngestExampleRequest) -> dict:
    if req.kind not in cellpy_adapter.EXAMPLE_RAW:
        raise HTTPException(400, f"Unknown raw example: {req.kind}")
    job = get_job_manager().submit("ingest-example", _ingest_example_job, req.kind, req.mass)
    return {"job_id": job.id}
