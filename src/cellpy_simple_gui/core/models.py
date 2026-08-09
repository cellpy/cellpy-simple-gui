"""Pydantic domain models shared by the core, the API and (as JSON) the UI."""

from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CapacityMode = Literal["gravimetric", "areal", "absolute"]
Direction = Literal["charge", "discharge"]
CycleMethod = Literal["forth-and-forth", "back-and-forth", "forth"]
# cellpy collected cycles layouts (legacy fig_pr_cell / fig_pr_cycle).
#
# "film" is presented here as a third layout because that is how it reads in the
# UI, but cellpy models it as a *kind* (``kind="film"`` + ``layout="per_cell"``,
# a histogram2d rather than lines). The translation happens in
# ``collect.curve_layout_kwargs`` — passing ``layout="film"`` straight to cellpy
# silently draws a line plot instead (see CELLPY_PAINPOINTS §29).
CyclesLayout = Literal["per_cell", "per_cycle", "film"]
# What the Cycles pane draws: voltage curves, or the differentials (#95).
CurveKind = Literal["voltage", "dqdv", "dvdq"]
# ICA plotter only accepts charge|discharge (not "both") — see CELLPY_PAINPOINTS §16.
IcaDirection = Literal["charge", "discharge", "both"]
# Resolved figure chrome (UI maps "match app" → light|dark before POST).
FigureTheme = Literal["light", "dark"]
# Curated plot colorways; "cellpy" keeps upstream/Plotly defaults.
ColorScheme = Literal["cellpy", "safe", "muted"]
CycleMode = Literal["anode", "cathode", "full_cell"]

# Human-friendly axis labels per capacity mode.
CAPACITY_UNITS: dict[CapacityMode, str] = {
    "gravimetric": "mAh/g",
    "areal": "mAh/cm²",
    "absolute": "mAh",
}


def _clean_axis_range(
    value: list[float | None] | None,
) -> list[float | None] | None:
    """Accept ``[lo, hi]`` with either end optional (blank → data extent).

    Both ends finite requires ``lo < hi``. A single finite end is kept as
    ``[lo, None]`` or ``[None, hi]``.
    """
    if not value or len(value) != 2:
        return None

    def _one(raw: object) -> float | None:
        if raw is None or raw == "":
            return None
        try:
            num = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return num if math.isfinite(num) else None

    lo, hi = _one(value[0]), _one(value[1])
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None and lo >= hi:
        return None
    return [lo, hi]


class CellMeta(BaseModel):
    """Everything the UI needs to know about one loaded cell.

    The heavy ``CellpyCell`` object lives in the in-memory library; this is the
    lightweight, serialisable projection of it.
    """

    id: str
    name: str
    source: str = "example"
    mass: float | None = None  # mg
    area: float | None = None  # cm^2
    nominal_capacity: float | None = None
    nom_cap_specifics: CapacityMode | None = None
    cycle_mode: CycleMode | None = None
    n_cycles: int = 0
    group: int = 1
    label: str = ""
    selected: bool = True
    color: str | None = None


class SummaryPlotSpec(BaseModel):
    """Drives a cellpy ``collect_summaries`` collection + its plot/export."""

    plot_type: str = "capacity_ce"
    basis: CapacityMode = "gravimetric"
    group_average: bool = False  # average per group (affects data/export)
    spread: bool = False  # mean ± std band (when grouped)
    # Legend click mutes whole journal group (cellpy default) vs one cell.
    # Meaningless when group_average=True (cellpy forces group_cells=False).
    group_legend_muting: bool = True
    max_cycle: Optional[int] = None
    # Independent y-scales by default so CE outliers don't crush capacity panels.
    # Maps to cellpy ``match_axes`` on the collected summary path.
    share_y: bool = False
    # Per-facet-row limits: summary column id → [lo, hi]. Either end may be
    # null (filled from that panel's data extent). Omitted keys autorange.
    # Non-empty values force independent axes (cellpy #804 / app #54).
    y_ranges: Optional[dict[str, list[Optional[float]]]] = None
    figure_theme: FigureTheme = "light"
    color_scheme: ColorScheme = "cellpy"
    title: str = "Cycle summary"

    @field_validator("y_ranges")
    @classmethod
    def _clean_y_ranges(cls, value: dict[str, list[float | None]] | None):
        if not value:
            return None
        cleaned: dict[str, list[float | None]] = {}
        for key, pair in value.items():
            cleaned_pair = _clean_axis_range(pair)
            if cleaned_pair is not None:
                cleaned[str(key)] = cleaned_pair
        return cleaned or None


class CyclesPlotSpec(BaseModel):
    """Drives a cellpy ``collect_cycles`` collection.

    With ``cell_id`` set: one library cell (Cell explorer).
    With ``cell_id`` omitted: selected library cells (Cycles collector tab).
    """

    cell_id: Optional[str] = None
    cycles: list[int] = Field(default_factory=list)
    mode: CapacityMode = "gravimetric"
    method: CycleMethod = "forth-and-forth"
    layout: CyclesLayout = "per_cycle"
    # dQ/dV and dV/dQ over the same cells and cycles (#95). They come from
    # collect_ica / collect_dva rather than collect_cycles, so `mode` / `method`
    # do not apply to them and `direction` / `voltage_resolution` do.
    curve_kind: CurveKind = "voltage"
    direction: IcaDirection = "charge"
    voltage_resolution: float = 0.005
    # Legend click mutes whole journal group vs one cell (Plotly).
    # Meaningless for layout=per_cell (cellpy forces group_cells=False).
    group_legend_muting: bool = True
    # Axis limits ``[lo, hi]``; either end may be null (filled from data).
    x_range: Optional[list[Optional[float]]] = None
    y_range: Optional[list[Optional[float]]] = None
    figure_theme: FigureTheme = "light"
    color_scheme: ColorScheme = "cellpy"
    title: str = ""

    @field_validator("x_range", "y_range")
    @classmethod
    def _clean_xy_range(cls, value: list[float | None] | None):
        return _clean_axis_range(value)


class IcaPlotSpec(BaseModel):
    """Drives a cellpy ``collect_ica`` collection for one cell (Cell explorer)."""

    cell_id: str
    cycles: list[int] = Field(default_factory=list)
    voltage_resolution: float = 0.005
    direction: IcaDirection = "charge"
    # Axis limits ``[lo, hi]``; either end may be null (filled from data).
    x_range: Optional[list[Optional[float]]] = None
    y_range: Optional[list[Optional[float]]] = None
    figure_theme: FigureTheme = "light"
    color_scheme: ColorScheme = "cellpy"
    title: str = ""

    @field_validator("x_range", "y_range")
    @classmethod
    def _clean_xy_range(cls, value: list[float | None] | None):
        return _clean_axis_range(value)


class DvaPlotSpec(IcaPlotSpec):
    """Differential voltage (dV/dQ vs capacity) for one cell — developer mode.

    Same controls as ICA: cellpy derives both from ``IcaOptions``, and the two
    views sit side by side in the Cell explorer.
    """


RawPlotType = Literal["voltage-current", "raw", "capacity", "capacity-current", "full"]

#: Points per trace kept when shipping a raw figure to the browser. cellpy plots
#: the whole raw frame (cellpy #867) — 18 MiB of JSON for one demo cell — so the
#: app thins it for transport.
DEFAULT_RAW_MAX_POINTS = 4000


class RawPlotSpec(BaseModel):
    """Raw time-series traces for one cell — developer mode."""

    cell_id: str
    plot_type: RawPlotType = "voltage-current"
    max_points: int = Field(default=DEFAULT_RAW_MAX_POINTS, ge=100, le=100_000)
    x_range: Optional[list[Optional[float]]] = None
    y_range: Optional[list[Optional[float]]] = None
    figure_theme: FigureTheme = "light"
    color_scheme: ColorScheme = "cellpy"
    title: str = ""

    @field_validator("x_range", "y_range")
    @classmethod
    def _clean_xy_range(cls, value: list[float | None] | None):
        return _clean_axis_range(value)


class CycleInfoPlotSpec(BaseModel):
    """Raw traces annotated with step/cycle information — developer mode.

    Cycle-scoped, so unlike :class:`RawPlotSpec` the payload is bounded by the
    selection: one trace per cycle, and no point cap is needed.
    """

    cell_id: str
    cycles: list[int] = Field(default_factory=list)
    figure_theme: FigureTheme = "light"
    color_scheme: ColorScheme = "cellpy"
    title: str = ""


class ExportSpec(BaseModel):
    """A plot spec plus the desired file format."""

    fmt: str = "csv"  # csv | xlsx | parquet | json
    summary: Optional[SummaryPlotSpec] = None
    cycles: Optional[CyclesPlotSpec] = None
    ica: Optional[IcaPlotSpec] = None
    dva: Optional[DvaPlotSpec] = None


class CellsExportSpec(BaseModel):
    """Optional explicit cell ids for library-cell export (default = selected)."""

    cell_ids: Optional[list[str]] = None


class JournalRowUpdate(BaseModel):
    """A single editable-grid change."""

    id: str
    group: Optional[int] = None
    label: Optional[str] = None
    selected: Optional[bool] = None
    mass: Optional[float] = None
    area: Optional[float] = None
    nominal_capacity: Optional[float] = None
    nom_cap_specifics: Optional[CapacityMode] = None
    cycle_mode: Optional[CycleMode] = None


class LoadExampleRequest(BaseModel):
    kinds: list[str] = Field(default_factory=lambda: ["cellpy", "old_cellpy", "rate"])


class LoadFilesRequest(BaseModel):
    paths: list[str]
    max_files: int = 10


class IngestRequest(BaseModel):
    """Import one or more raw instrument files with shared metadata."""

    paths: list[str]
    max_files: int = 10
    instrument: str
    model: Optional[str] = None
    mass: Optional[float] = None  # mg
    area: Optional[float] = None  # cm^2
    nominal_capacity: Optional[float] = None
    nom_cap_specifics: Optional[CapacityMode] = None
    cycle_mode: Optional[CycleMode] = None


class IngestExampleRequest(BaseModel):
    kind: str = "neware"  # one of cellpy_adapter.EXAMPLE_RAW
    mass: Optional[float] = None
