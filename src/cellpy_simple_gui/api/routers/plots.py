"""Plot endpoints — return Plotly figure JSON built by the core."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ...config import get_settings
from ...core import cellpy_adapter, collect, plotting
from ...core.library import get_library
from ...core.models import (
    CycleInfoPlotSpec,
    CyclesPlotSpec,
    DvaPlotSpec,
    IcaPlotSpec,
    RawPlotSpec,
    SummaryPlotSpec,
)

router = APIRouter()


@router.get("/plot-types")
def plot_types(basis: str = "gravimetric") -> dict:
    """Curated summary plot types, with panel ids for the current capacity basis.

    Developer mode appends every family cellpy registers, each marked with the
    columns the loaded cells are missing so an unusable one is visibly greyed
    out rather than silently empty (#97).
    """
    types = []
    for entry in collect.SUMMARY_PLOT_TYPES:
        panel_basis = basis if entry.get("basis") else "absolute"
        types.append(
            {
                **entry,
                "source": "curated",
                "panels": collect.summary_panels_for(entry["id"], panel_basis),
            }
        )

    dev = get_settings().dev_mode
    if dev:
        # Availability depends on what is actually loaded, so resolve against
        # the current selection rather than a static schema.
        types.extend(collect.registry_plot_types(get_library().selected()))
    return {"types": types, "dev_mode": dev}


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


def _cycles_records(spec: CyclesPlotSpec):
    """One cell when ``cell_id`` is set; otherwise library selection."""
    lib = get_library()
    if spec.cell_id:
        try:
            return [lib.get(spec.cell_id)]
        except KeyError:
            raise HTTPException(404, "No such cell")
    return lib.selected()


@router.get("/plots/cycles/bounds")
def selected_cycles_bounds() -> dict:
    """Union of cycle numbers across currently selected cells (Cycles tab)."""
    records = get_library().selected()
    numbers: set[int] = set()
    for rec in records:
        numbers.update(cellpy_adapter.cycle_numbers(rec.cell))
    ordered = sorted(numbers)
    return {
        "n_cells": len(records),
        "min": ordered[0] if ordered else 0,
        "max": ordered[-1] if ordered else 0,
    }


@router.post("/plots/cycles")
def cycles_plot(spec: CyclesPlotSpec) -> Response:
    figure_json = plotting.cycles_figure(_cycles_records(spec), spec)
    return _figure_response(figure_json)


@router.post("/plots/ica")
def ica_plot(spec: IcaPlotSpec) -> Response:
    lib = get_library()
    try:
        rec = lib.get(spec.cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")
    figure_json = plotting.ica_figure(rec, spec)
    return _figure_response(figure_json)


def require_dev_mode() -> None:
    """Guard endpoints that only exist in developer mode (#97)."""
    if not get_settings().dev_mode:
        raise HTTPException(
            403, "This view is only available in developer mode (start with --dev)."
        )


def _dev_cell(cell_id: str):
    """Resolve a cell for a developer-mode view."""
    require_dev_mode()
    try:
        return get_library().get(cell_id)
    except KeyError:
        raise HTTPException(404, "No such cell")


@router.post("/plots/dva")
def dva_plot(spec: DvaPlotSpec) -> Response:
    """Differential voltage (dV/dQ vs capacity) for one cell — developer mode."""
    return _figure_response(plotting.dva_figure(_dev_cell(spec.cell_id), spec))


@router.post("/plots/raw")
def raw_plot(spec: RawPlotSpec) -> Response:
    """Raw time-series traces for one cell — developer mode."""
    return _figure_response(plotting.raw_figure(_dev_cell(spec.cell_id), spec))


@router.post("/plots/cycle-info")
def cycle_info_plot(spec: CycleInfoPlotSpec) -> Response:
    """Raw traces with step/cycle annotations — developer mode."""
    return _figure_response(plotting.cycle_info_figure(_dev_cell(spec.cell_id), spec))
