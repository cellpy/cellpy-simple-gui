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
from .models import CAPACITY_UNITS, CyclesPlotSpec, IcaPlotSpec, SummaryPlotSpec


def summary_figure(records: list[CellRecord], spec: SummaryPlotSpec) -> str:
    if not records:
        return collect._empty_figure_json(
            "Select one or more cells to plot the cycle summary.",
            figure_theme=spec.figure_theme,
        )
    columns = collect.summary_columns_for(spec.plot_type, spec.basis)
    # cellpy ≥2.1.2 averages multi-member groups even when a singleton group is
    # present and returns them in one collection (#816), so no app-side split.
    collection = collect.summary_collection(
        records,
        columns=columns,
        group_it=spec.group_average,
        max_cycle=spec.max_cycle,
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


def cycles_figure(records: list[CellRecord], spec: CyclesPlotSpec) -> str:
    if not records:
        return collect._empty_figure_json(
            "Select one or more cells to plot cycle curves.",
            figure_theme=spec.figure_theme,
        )
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to plot the voltage curves.",
            figure_theme=spec.figure_theme,
        )
    collection = collect.cycles_collection(
        records, cycles=cycles, mode=spec.mode, method=spec.method
    )
    # cellpy cycles_plotter defaults x_unit="mAh/g" and ignores collection mode (#72).
    x_unit = CAPACITY_UNITS.get(spec.mode, CAPACITY_UNITS["gravimetric"])
    return collect.figure_json(
        collection,
        family_kind="cycles",
        layout=spec.layout,
        group_legend_muting=spec.group_legend_muting,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_unit=x_unit,
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
