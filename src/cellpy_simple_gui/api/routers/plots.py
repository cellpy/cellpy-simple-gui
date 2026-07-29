"""Plot endpoints — return Plotly figure JSON built by the core."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ...core import cellpy_adapter, collect, plotting
from ...core.library import get_library
from ...core.models import CyclesPlotSpec, SummaryPlotSpec

router = APIRouter()


@router.get("/plot-types")
def plot_types() -> dict:
    return {"types": collect.SUMMARY_PLOT_TYPES}


def _figure_response(figure_json: str) -> Response:
    # figure_json is already a JSON string (numpy-safe) from plotly.io.to_json
    return Response(content=figure_json, media_type="application/json")


@router.post("/plots/summary")
def summary_plot(spec: SummaryPlotSpec) -> Response:
    lib = get_library()
    figure_json = plotting.summary_figure(lib.selected(), spec)
    return _figure_response(figure_json)


@router.get("/cells/{cell_id}/cycles")
def cell_cycles(cell_id: str) -> dict:
    lib = get_library()
    try:
        rec = lib.get(cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    numbers = cellpy_adapter.cycle_numbers(rec.cell)
    return {
        "cell_id": cell_id,
        "name": rec.label or rec.name,
        "cycles": numbers,
        "min": min(numbers) if numbers else 0,
        "max": max(numbers) if numbers else 0,
    }


@router.post("/plots/cycles")
def cycles_plot(spec: CyclesPlotSpec) -> Response:
    lib = get_library()
    try:
        rec = lib.get(spec.cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    figure_json = plotting.cycles_figure(rec, spec)
    return _figure_response(figure_json)
