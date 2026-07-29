"""Export endpoints: CSV data and (optional) static figure images."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from ...core import export as export_core
from ...core.library import get_library
from ...core.models import CyclesPlotSpec, SummaryPlotSpec

router = APIRouter()


@router.post("/export/summary.csv")
def export_summary_csv(spec: SummaryPlotSpec) -> Response:
    data = export_core.summary_csv(get_library().selected(), spec)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=summary.csv"},
    )


@router.post("/export/cycles.csv")
def export_cycles_csv(spec: CyclesPlotSpec) -> Response:
    try:
        rec = get_library().get(spec.cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    data = export_core.cycles_csv(rec, spec)
    fname = f"cycles_{rec.label or rec.name}.csv".replace(" ", "_")
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.post("/export/figure")
def export_figure(
    figure_json: str = Body(..., embed=True),
    fmt: str = Body("png", embed=True),
) -> Response:
    try:
        data = export_core.figure_image(figure_json, fmt=fmt)
    except Exception as exc:  # noqa: BLE001 - kaleido is optional / may be missing
        raise HTTPException(
            501,
            f"Static image export unavailable ({exc}). Install the 'export' extra "
            "(kaleido), or use the camera icon on the chart to save a PNG.",
        )
    media = "application/pdf" if fmt == "pdf" else f"image/{fmt}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=figure.{fmt}"},
    )
