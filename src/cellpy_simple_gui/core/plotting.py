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
            "Select one or more cells to plot the cycle summary."
        )
    columns = collect.summary_columns(
        spec.basis, spec.show_charge, spec.show_discharge, spec.show_efficiency
    )
    collection = collect.summary_collection(
        records, columns=columns, group_it=spec.group_average, max_cycle=spec.max_cycle
    )
    return collect.figure_json(collection, spread=spec.spread)


def cycles_figure(record: CellRecord, spec: CyclesPlotSpec) -> str:
    cycles = tuple(sorted(set(spec.cycles)))
    if not cycles:
        return collect._empty_figure_json(
            "Pick one or more cycles to plot the voltage curves."
        )
    collection = collect.cycles_collection(
        [record], cycles=cycles, mode=spec.mode, method=spec.method
    )
    return collect.figure_json(collection, family_kind="cycles", layout="per_cell")
