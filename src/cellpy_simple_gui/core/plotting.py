"""Figure generation — thin delegation to cellpy's own collect + plotting.

We no longer hand-roll matplotlib/plotly figures from raw dataframes. Instead we
build a cellpy :class:`~cellpy.collect.Collection` (via :mod:`.collect`) and let
cellpy's plotting subsystem draw it, so the app's charts are exactly cellpy's
charts (curated plot families, per-cell cycle isolation, group handling) with
just a light restyle to match the app shell.
"""

from __future__ import annotations

from . import cellpy_adapter, collect
from .cycle_report import CycleReport, build_reports, compress_ranges, messages
from .library import CellRecord
from .models import (
    CAPACITY_UNITS,
    ComparePlotSpec,
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
        # cellpy ≥2.1.5 draws charge and discharge of one quantity on one
        # panel. This app's y-range widgets and facet order are one panel
        # per summary column, so keep that layout.
        combine_directions=False,
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


def _cycle_availability(
    records: list[CellRecord],
) -> tuple[list[str], dict[str, set[int]]]:
    """Batch label and cycle numbers per record, in record order (#175)."""
    labels = collect.batch_keys(records)
    available = {
        label: set(cellpy_adapter.cycle_numbers(rec.cell))
        for label, rec in zip(labels, records, strict=True)
    }
    return labels, available


def _nothing_to_draw_json(
    reports: list[CycleReport], *, figure_theme: str, headline: str | None = None
) -> str:
    """Empty figure that says *why* nothing was drawn (#175)."""
    notes = messages(reports)
    text = headline or ("Nothing to draw — " + "; ".join(notes) + ".")
    return collect._empty_figure_json(text, figure_theme=figure_theme, warnings=notes)


def _single_cell_reports(
    records: list[CellRecord],
    cycles: tuple[int, ...],
    available: dict[str, set[int]],
    collection,
) -> list[CycleReport]:
    """Missing + unreadable cycles for the one-cell explorer views.

    Only judged for a single record: across several selected cells (the Cycles
    tab) each cell lacking some cycle is expected, not a warning.
    """
    if len(records) != 1:
        return []
    (label,) = available
    present = collect.present_cycle_pairs(collection)
    return build_reports({label: cycles}, available, present)


def _guard_no_cycles(
    records: list[CellRecord],
    cycles: tuple[int, ...],
    available: dict[str, set[int]],
    *,
    figure_theme: str,
) -> str | None:
    """Empty-figure JSON when *no* record has *any* requested cycle, else None.

    cellpy raises (``KeyError('cycle_num')`` / ``AttributeError('cycle')``)
    rather than returning an empty frame in that case, which used to surface
    as "Could not render this plot" (#175).
    """
    if any(c in have for have in available.values() for c in cycles):
        return None
    reports = build_reports({label: cycles for label in available}, available, None)
    headline = None
    if len(records) > 1:
        word = "cycle" if len(cycles) == 1 else "cycles"
        headline = (
            f"None of the {len(records)} selected cells has {word} "
            f"{compress_ranges(cycles)}."
        )
    return _nothing_to_draw_json(reports, figure_theme=figure_theme, headline=headline)


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
    _, available = _cycle_availability(records)
    guard = _guard_no_cycles(records, cycles, available, figure_theme=spec.figure_theme)
    if guard is not None:
        return guard
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
        notes = messages(_single_cell_reports(records, cycles, available, collection))
        # cellpy ≥2.1.2 picks the half-cycle in the plotter (#821).
        return collect.figure_json(
            collection, direction=spec.direction, warnings=notes, **common
        )

    collection = collect.cycles_collection(
        records, cycles=cycles, mode=spec.mode, method=spec.method
    )
    notes = messages(_single_cell_reports(records, cycles, available, collection))
    # cellpy cycles_plotter defaults x_unit="mAh/g" and ignores collection mode (#72).
    x_unit = CAPACITY_UNITS.get(spec.mode, CAPACITY_UNITS["gravimetric"])
    return collect.figure_json(collection, x_unit=x_unit, warnings=notes, **common)


#: ``(record, cycles)`` per pick, in pick order — what the compare router
#: resolves from a :class:`ComparePlotSpec` once the cells are looked up.
ComparePicks = list[tuple[CellRecord, list[int]]]


def compare_collection(
    picks: ComparePicks, spec: ComparePlotSpec
) -> tuple[object | None, list[CycleReport]]:
    """Collect the picked cells over the *union* of their cycles, then narrow.

    Shared by the figure and the data export so both see the same rows (#169).
    Returns ``(collection, reports)``; the collection is ``None`` when nothing
    is picked or no picked cycle exists in its cell, and ``reports`` names
    every ``(cell, cycle)`` that could not be delivered (#175).
    """
    picks = [(rec, cycles) for rec, cycles in picks if cycles]
    if not picks:
        return None, []
    records = [rec for rec, _ in picks]
    # Frame labels come from the batch, not the library id.
    labels, available = _cycle_availability(records)
    requested = {
        label: list(cycles) for label, (_, cycles) in zip(labels, picks, strict=True)
    }
    # cellpy raises rather than returning an empty frame when no cell has any
    # requested cycle (painpoint §37), so settle that before collecting.
    existing = {
        label: [c for c in cycles if c in available[label]]
        for label, cycles in requested.items()
    }
    union = tuple(sorted({c for cycles in existing.values() for c in cycles}))
    if not union:
        return None, build_reports(requested, available, None)
    if spec.curve_kind in ("dqdv", "dvdq"):
        collect_fn = (
            collect.ica_collection if spec.curve_kind == "dqdv" else collect.dva_collection
        )
        collection = collect_fn(
            records, cycles=union, voltage_resolution=spec.voltage_resolution
        )
    else:
        collection = collect.cycles_collection(
            records, cycles=union, mode=spec.mode, method=spec.method
        )
    pairs = {(label, cycle) for label, cycles in existing.items() for cycle in cycles}
    collection = collect.restrict_to_cycle_pairs(collection, pairs)
    reports = build_reports(requested, available, collect.present_cycle_pairs(collection))
    return collection, reports


def compare_figure(picks: ComparePicks, spec: ComparePlotSpec) -> str:
    """Curves from several cells, each with its own cycles, in one figure (#169).

    Drawn through cellpy's ``per_cell`` layout; ``layout="overlay"`` then folds
    the facets onto one axis pair (:func:`collect._overlay_facets`). Cycles a
    cell could not deliver are reported in ``layout.meta.warnings`` (#175).
    """
    collection, reports = compare_collection(picks, spec)
    if collection is None:
        if reports:
            return _nothing_to_draw_json(reports, figure_theme=spec.figure_theme)
        return collect._empty_figure_json(
            _CURVE_PROMPTS.get(spec.curve_kind, _CURVE_PROMPTS["voltage"]),
            figure_theme=spec.figure_theme,
        )
    common = dict(
        family_kind=_CURVE_FAMILIES.get(spec.curve_kind, "cycles"),
        layout="per_cell",
        overlay=spec.layout == "overlay",
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
        warnings=messages(reports),
    )
    if spec.curve_kind in ("dqdv", "dvdq"):
        return collect.figure_json(collection, direction=spec.direction, **common)
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
    _, available = _cycle_availability([record])
    guard = _guard_no_cycles([record], cycles, available, figure_theme=spec.figure_theme)
    if guard is not None:
        return guard
    collection = collect.dva_collection(
        [record], cycles=cycles, voltage_resolution=spec.voltage_resolution
    )
    return collect.figure_json(
        collection,
        family_kind="dva",
        layout="per_cell",
        direction=spec.direction,
        warnings=messages(_single_cell_reports([record], cycles, available, collection)),
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
    _, available = _cycle_availability([record])
    guard = _guard_no_cycles([record], cycles, available, figure_theme=spec.figure_theme)
    if guard is not None:
        return guard
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
        warnings=messages(_single_cell_reports([record], cycles, available, collection)),
        figure_theme=spec.figure_theme,
        color_scheme=spec.color_scheme,
        x_range=spec.x_range,
        y_range=spec.y_range,
    )
