"""Figure generation — thin delegation to cellpy's own collect + plotting.

We no longer hand-roll matplotlib/plotly figures from raw dataframes. Instead we
build a cellpy :class:`~cellpy.collect.Collection` (via :mod:`.collect`) and let
cellpy's plotting subsystem draw it, so the app's charts are exactly cellpy's
charts (curated plot families, per-cell cycle isolation, group handling) with
just a light restyle to match the app shell.
"""

from __future__ import annotations

from . import collect
from .library import CellRecord
from .models import (
    CAPACITY_UNITS,
    CycleInfoPlotSpec,
    CyclesPlotSpec,
    DvaPlotSpec,
    IcaPlotSpec,
    RawPlotSpec,
    SummaryPlotSpec,
)


def summary_figure(records: list[CellRecord], spec: SummaryPlotSpec) -> str:
    if not records:
        return collect._empty_figure_json(
            "Select one or more cells to plot the cycle summary.",
            figure_theme=spec.figure_theme,
        )
    columns = collect.summary_columns_for(spec.plot_type, spec.basis, records)
    if not columns:
        return collect._empty_figure_json(
            "This cellpy plot family declares no summary columns.",
            figure_theme=spec.figure_theme,
        )
    # A family names its columns whether or not the data has them, so say which
    # are missing rather than rendering a blank chart (#97). Judge that on the
    # pre-derivation inputs — collect makes *_cv and mod_01_* itself (#106).
    missing = collect.missing_summary_columns(
        collect.summary_required_columns(spec.plot_type, spec.basis, records), records
    )
    if missing:
        return collect._empty_figure_json(
            "These cells have no " + ", ".join(missing)
            + " — pick a plot type the loaded data supports.",
            figure_theme=spec.figure_theme,
        )
    # cellpy ≥2.1.2 averages multi-member groups even when a singleton group is
    # present and returns them in one collection (#816), so no app-side split.
    collection = collect.summary_collection(
        records,
        columns=columns,
        group_it=spec.group_average,
        max_cycle=spec.max_cycle,
        options=collect.summary_options_for(spec.plot_type, records),
    )
    y_ranges = spec.y_ranges or {}
    return collect.figure_json(
        collection,
        spread=spec.spread,
        # cellpy prefers share_y; match_axes kept as alias for older paths.
        share_y=spec.share_y,
        match_axes=spec.share_y,
        y_ranges=y_ranges,
        group_legend_muting=spec.group_legend_muting,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        # Unit-bearing titles; cellpy defaults are pretty but unit-less (§18 / #38).
        y_label_mapper=collect.summary_y_label_mapper(columns),
        # Honour column order on long (group-avg) frames; cellpy otherwise
        # lets Plotly unique-order facets (#81 / painpoint §20).
        category_orders={"variable": list(columns)},
    )


#: Which collector and cellpy family each Cycles-pane curve kind uses (#95).
_CURVE_FAMILIES: dict[str, str] = {
    "voltage": "cycles",
    "dqdv": "ica",
    "dvdq": "dva",
}

_CURVE_PROMPTS: dict[str, str] = {
    "voltage": "Pick one or more cycles to plot the voltage curves.",
    "dqdv": "Pick one or more cycles to plot dQ/dV.",
    "dvdq": "Pick one or more cycles to plot dV/dQ.",
}


def cycles_figure(records: list[CellRecord], spec: CyclesPlotSpec) -> str:
    if not records:
        return collect._empty_figure_json(
            "Select one or more cells to plot cycle curves.",
            figure_theme=spec.figure_theme,
        )
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            _CURVE_PROMPTS.get(spec.curve_kind, _CURVE_PROMPTS["voltage"]),
            figure_theme=spec.figure_theme,
        )
    common = dict(
        family_kind=_CURVE_FAMILIES.get(spec.curve_kind, "cycles"),
        group_legend_muting=spec.group_legend_muting,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
        # Straight through: cellpy ≥2.1.3 accepts layout="film" as an alias for
        # the film *kind* and raises on an unknown layout (#874). Before that it
        # silently drew lines, and this line was a translation shim.
        layout=spec.layout,
    )
    if spec.curve_kind in ("dqdv", "dvdq"):
        # Differentials come from collect_ica / collect_dva across the same
        # cells and cycles, so mode/method (a cycles-curve idea) do not apply.
        collect_fn = (
            collect.ica_collection if spec.curve_kind == "dqdv" else collect.dva_collection
        )
        collection = collect_fn(
            records, cycles=cycles, voltage_resolution=spec.voltage_resolution
        )
        # cellpy ≥2.1.2 picks the half-cycle in the plotter (#821).
        return collect.figure_json(collection, direction=spec.direction, **common)

    collection = collect.cycles_collection(
        records, cycles=cycles, mode=spec.mode, method=spec.method
    )
    # cellpy cycles_plotter defaults x_unit="mAh/g" and ignores collection mode (#72).
    x_unit = CAPACITY_UNITS.get(spec.mode, CAPACITY_UNITS["gravimetric"])
    return collect.figure_json(collection, x_unit=x_unit, **common)


def raw_figure(record: CellRecord, spec: RawPlotSpec) -> str:
    """Raw time-series traces for one cell — developer mode."""
    return collect.raw_figure_json(
        record.cell,
        plot_type=spec.plot_type,
        max_points=spec.max_points,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
    )


def cycle_info_figure(record: CellRecord, spec: CycleInfoPlotSpec) -> str:
    """Raw traces with step/cycle annotations — developer mode."""
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to show step and cycle info.",
            figure_theme=spec.figure_theme,
        )
    return collect.cycle_info_figure_json(
        record.cell,
        cycles=cycles,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
    )


def dva_figure(record: CellRecord, spec: DvaPlotSpec) -> str:
    """Differential voltage (dV/dQ vs capacity) for one cell — developer mode."""
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to plot dV/dQ.",
            figure_theme=spec.figure_theme,
        )
    collection = collect.dva_collection(
        [record], cycles=cycles, voltage_resolution=spec.voltage_resolution
    )
    return collect.figure_json(
        collection,
        family_kind="dva",
        layout="per_cell",
        direction=spec.direction,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
    )


def ica_figure(record: CellRecord, spec: IcaPlotSpec) -> str:
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to plot dQ/dV.",
            figure_theme=spec.figure_theme,
        )
    collection = collect.ica_collection(
        [record],
        cycles=cycles,
        voltage_resolution=spec.voltage_resolution,
    )
    return collect.figure_json(
        collection,
        family_kind="ica",
        layout="per_cell",
        # cellpy ≥2.1.2 selects the half-cycle in ica_plotter (#821): charge /
        # discharge filter, "both" overlays with line_dash.
        direction=spec.direction,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
    )
