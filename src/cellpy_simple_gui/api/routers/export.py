"""Export endpoints: collected data as csv / xlsx / parquet / json."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ...core import collect, export as export_core
from ...core.library import get_library
from ...core.models import CyclesPlotSpec, SummaryPlotSpec

router = APIRouter()

_EXT = {"csv": "csv", "xlsx": "xlsx", "parquet": "parquet", "json": "json"}


def _check_fmt(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in collect.EXPORT_FORMATS:
        raise HTTPException(400, f"Unsupported format '{fmt}'. Use one of {collect.EXPORT_FORMATS}.")
    return fmt


def _file(data: bytes, media: str, name: str) -> Response:
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )


@router.post("/export/summary")
def export_summary(spec: SummaryPlotSpec, fmt: str = "csv") -> Response:
    fmt = _check_fmt(fmt)
    records = get_library().selected()
    if not records:
        raise HTTPException(400, "No cells selected.")
    data, media = export_core.summary_export(records, spec, fmt)
    return _file(data, media, f"summary.{_EXT[fmt]}")


@router.post("/export/cycles")
def export_cycles(spec: CyclesPlotSpec, fmt: str = "csv") -> Response:
    fmt = _check_fmt(fmt)
    try:
        rec = get_library().get(spec.cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    data, media = export_core.cycles_export(rec, spec, fmt)
    name = f"cycles_{rec.label or rec.name}".replace(" ", "_")
    return _file(data, media, f"{name}.{_EXT[fmt]}")
