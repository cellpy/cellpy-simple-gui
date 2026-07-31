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
from .models import CyclesPlotSpec, SummaryPlotSpec


def summary_figure(records: list[CellRecord], spec: SummaryPlotSpec) -> str:
    if not records:
        return collect._empty_figure_json(
            "Select one or more cells to plot the cycle summary.",
            figure_theme=spec.figure_theme,
        )
    columns = collect.summary_columns_for(spec.plot_type, spec.basis)
    parts = collect.summary_collections(
        records,
        columns=columns,
        group_it=spec.group_average,
        max_cycle=spec.max_cycle,
    )
    y_ranges = spec.y_ranges or {}
    return collect.figures_json(
        parts,
        spread=spec.spread,
        # cellpy prefers share_y; match_axes kept as alias for older paths.
        share_y=spec.share_y,
        match_axes=spec.share_y,
        y_ranges=y_ranges,
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
    )


def cycles_figure(record: CellRecord, spec: CyclesPlotSpec) -> str:
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to plot the voltage curves.",
            figure_theme=spec.figure_theme,
        )
    collection = collect.cycles_collection(
        [record], cycles=cycles, mode=spec.mode, method=spec.method
    )
    return collect.figure_json(
        collection,
        family_kind="cycles",
        layout="per_cell",
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
    )
