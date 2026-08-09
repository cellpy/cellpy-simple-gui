"""Bridge the in-memory library into cellpy's own collect / plot / export stack.

Rather than re-implementing summaries, grouping and multi-cell plotting, we hand
our loaded cells to cellpy's :mod:`cellpy.collect` subsystem and let it do the
work — so grouping, spread, per-cell cycle isolation, the curated plot families
and multi-format export all come "for free" and stay consistent with cellpy.

Since cellpy 2.1.1 the glue is a one-liner: :func:`cellpy.collect.from_cells`
builds a real :class:`~cellpy.batch.Batch` from already-loaded cells (added in
response to issue #787), so we no longer maintain a hand-rolled batch shim.
"""

from __future__ import annotations

import io
import logging

import plotly.io as pio
from cellpy.collect import collect_cycles, collect_ica, collect_summaries, from_cells
from cellpy.collect.options import CurveOptions, IcaOptions

from .library import PALETTE, CellRecord

log = logging.getLogger(__name__)

# Curated plot colorways (UI swatches stay on library.PALETTE independently).
COLOR_SCHEMES: dict[str, list[str] | None] = {
    "cellpy": None,  # keep upstream / Plotly defaults
    "safe": list(PALETTE),
    "muted": [
        "#6B7C93", "#C48A5A", "#6A9A6E", "#B86B6B", "#6E9A96",
        "#C4B05A", "#9A7A9E", "#C48A92", "#8A7460", "#9A9690",
    ],
}

_THEME_TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font_color": "#1f2933",
        "gridcolor": "#eceff3",
        "linecolor": "#c7ccd4",
        "tickcolor": "#c7ccd4",
        "legend_bg": "rgba(255,255,255,0.6)",
        "annotation": "#7b8794",
    },
    "dark": {
        "paper_bgcolor": "#1a1f26",
        "plot_bgcolor": "#1a1f26",
        "font_color": "#e6edf3",
        "gridcolor": "#2d3640",
        "linecolor": "#4a5560",
        "tickcolor": "#4a5560",
        "legend_bg": "rgba(26,31,38,0.75)",
        "annotation": "#9aa5b1",
    },
}


# --------------------------------------------------------------------------- #
# Batch from the library
# --------------------------------------------------------------------------- #


def _batch(records: list[CellRecord]):
    """Build a cellpy ``Batch`` from library records (labels/groups/selection)."""
    cells: dict[str, object] = {}
    groups: dict[str, int] = {}
    selected: dict[str, bool] = {}
    group_labels: dict[int, str] = {}
    seen: dict[str, int] = {}
    for rec in records:
        key = rec.label or rec.name or rec.id
        if key in seen:
            seen[key] += 1
            key = f"{key} ({seen[key]})"
        else:
            seen[key] = 1
        cells[key] = rec.cell
        groups[key] = rec.group
        selected[key] = rec.selected
        group_labels[rec.group] = f"group {rec.group}"
    return from_cells(cells, groups=groups, selected=selected, group_labels=group_labels)


# --------------------------------------------------------------------------- #
# Column helpers
# --------------------------------------------------------------------------- #

_BASIS_SUFFIX = {"gravimetric": "_gravimetric", "areal": "_areal", "absolute": ""}

#: Curated summary plot types, drawn from cellpy's summary vocabulary. Each maps
#: to a set of ``cell.data.summary`` columns that render through the collected
#: summary path. ``basis`` = whether the capacity basis (grav/areal/abs) applies.
SUMMARY_PLOT_TYPES = [
    {"id": "capacity_ce", "label": "Capacity + coulombic efficiency", "basis": True},
    {"id": "capacity", "label": "Capacity (charge & discharge)", "basis": True},
    {"id": "charge_capacity", "label": "Charge capacity", "basis": True},
    {"id": "discharge_capacity", "label": "Discharge capacity", "basis": True},
    {"id": "coulombic_efficiency", "label": "Coulombic efficiency", "basis": False},
    {"id": "cumulated_ce", "label": "Cumulated coulombic efficiency", "basis": False},
    {"id": "capacity_loss", "label": "Capacity loss", "basis": True},
    {"id": "end_voltages", "label": "End-of-charge / discharge voltage", "basis": False},
    {"id": "internal_resistance", "label": "Internal resistance (IR)", "basis": False},
    {"id": "c_rate", "label": "C-rate", "basis": False},
]


#: Prefix marking a plot type that came from cellpy's registry rather than the
#: curated list, so ``summary_columns_for`` can tell the two apart.
FAMILY_PREFIX = "family:"


#: cellpy's public plot entry a summary family belongs to. Restricting the menu
#: to this one keeps ``raw`` / ``ica`` / ``dva`` / ``cycle_info`` out of it —
#: those are separate entry points with their own tabs in the app.
SUMMARY_ENTRY_POINT = "summary_plot"


def registry_plot_types(records: list[CellRecord] | None = None) -> list[dict]:
    """Every summary family cellpy registers, marked available or not (#97).

    Availability is judged on what a family *asks the summary for*, not on the
    columns it ends up drawing: ``family.summary_options()`` (cellpy 2.1.2,
    #868) reports the CV split and the transforms that manufacture the rest at
    collect time. Checking the drawn names instead made every CV-split and
    full-cell family look unplottable (#106).
    """
    try:
        from cellpy.plotting import registry
    except Exception:  # noqa: BLE001 - dev extra must never break the app
        log.warning("cellpy plot registry unavailable", exc_info=True)
        return []

    hdr, available = _summary_schema(records)
    # Without a loaded cell there is no summary header to resolve column names
    # against, so availability is unknown — say that rather than implying the
    # data lacks the columns.
    no_cells = hdr is None
    out: list[dict] = []
    for name, description in registry.families(entry_point=SUMMARY_ENTRY_POINT):
        entry: dict = {
            "id": f"{FAMILY_PREFIX}{name}",
            "label": description or name,
            "family": name,
            "basis": False,  # the family name already fixes the basis
            "source": "registry",
        }
        try:
            columns = list(registry.get(name).columns(hdr)) if hdr is not None else []
            required = list(_family_required_columns(name, hdr)) if hdr is not None else []
        except Exception as exc:  # noqa: BLE001 - a broken family is data, not a crash
            entry.update(columns=[], missing=[], unavailable_reason=str(exc))
            out.append(entry)
            continue
        missing = [c for c in required if available is not None and c not in available]
        entry["columns"] = columns
        entry["missing"] = missing
        if no_cells:
            entry["unavailable_reason"] = "load cells to see whether this family applies"
        elif not columns:
            entry["unavailable_reason"] = "this family declares no summary columns"
        elif missing:
            entry["unavailable_reason"] = "missing " + ", ".join(missing)
        out.append(entry)
    return out


def _family_required_columns(family: str, hdr) -> tuple[str, ...]:
    """Summary columns a family needs *before* collect-time derivation.

    ``family.columns(hdr)`` names what ends up on the chart, which includes
    columns collect manufactures: ``*_cv`` / ``*_non_cv`` from the CV split and
    ``mod_01_*`` from a transform. ``summary_options().columns`` is the honest
    input list, so that is what availability is judged on.
    """
    from cellpy.plotting import registry

    fam = registry.get(family)
    try:
        return tuple(fam.summary_options(hdr).columns)
    except Exception:  # noqa: BLE001 - fall back to the drawn names
        log.warning("family %r has no summary_options; using columns()", family, exc_info=True)
        return tuple(fam.columns(hdr))


def family_summary_options(family: str, records: list[CellRecord] | None = None):
    """Ready :class:`SummaryOptions` for a registry family, or ``None``.

    Carries the family's own ``partition_by_cv`` and transforms, so collecting
    with it produces the columns the family actually plots (#868).
    """
    from cellpy.plotting import registry

    hdr, _ = _summary_schema(records)
    if hdr is None:
        return None
    try:
        return registry.get(family).summary_options(hdr)
    except Exception:  # noqa: BLE001 - plain column collect still works
        log.warning("could not build summary options for %r", family, exc_info=True)
        return None


def _summary_schema(records: list[CellRecord] | None):
    """``(header, available_columns)`` across the loaded cells, or ``(None, None)``.

    Columns are unioned rather than taken from the first cell: a collected plot
    spans the whole selection, so one odd cell should not make a family look
    unplottable for the rest.
    """
    hdr = None
    available: set[str] | None = None
    for rec in records or []:
        try:
            hdr = hdr if hdr is not None else rec.cell.schema.summary
        except Exception:  # noqa: BLE001 - try the next cell
            continue
        try:
            cols = set(rec.cell.data.summary.columns)
        except Exception:  # noqa: BLE001 - schema known, summary not readable
            continue
        available = cols if available is None else (available | cols)
    return hdr, available


def missing_summary_columns(
    columns: tuple[str, ...] | list[str], records: list[CellRecord] | None
) -> list[str]:
    """Which of ``columns`` the loaded cells do not actually carry.

    A family's ``column_builder`` names columns whether or not the data has
    them, so this is what separates "will plot" from "will render blank".
    """
    _, available = _summary_schema(records)
    if available is None:
        return []
    return [c for c in columns if c not in available]


def family_columns(family: str, records: list[CellRecord] | None = None) -> tuple[str, ...]:
    """Columns for a registry family, resolved against the loaded cells."""
    from cellpy.plotting import registry

    hdr, _ = _summary_schema(records)
    if hdr is None:
        return ()
    return tuple(registry.get(family).columns(hdr))


def summary_options_for(plot_type: str, records: list[CellRecord] | None = None):
    """Collect options for a plot type, or ``None`` for the curated ones.

    Only a cellpy family carries its own options; the curated types are plain
    column selections.
    """
    if not plot_type.startswith(FAMILY_PREFIX):
        return None
    return family_summary_options(plot_type[len(FAMILY_PREFIX) :], records)


def summary_required_columns(
    plot_type: str, basis: str, records: list[CellRecord] | None = None
) -> tuple[str, ...]:
    """The summary columns the data must already carry for this plot type.

    Same as :func:`summary_columns_for` for the curated types, but for a cellpy
    family it is the pre-derivation input set — collect makes the ``*_cv`` and
    ``mod_01_*`` columns itself, so demanding them up front would reject
    families that plot perfectly well (#106).
    """
    if plot_type.startswith(FAMILY_PREFIX):
        family = plot_type[len(FAMILY_PREFIX) :]
        hdr, _ = _summary_schema(records)
        if hdr is None:
            return ()
        try:
            return _family_required_columns(family, hdr)
        except Exception:  # noqa: BLE001 - fall back rather than break the plot
            log.warning("unknown cellpy plot family %r", family, exc_info=True)
            return ()
    return summary_columns_for(plot_type, basis, records)


def summary_columns_for(
    plot_type: str, basis: str, records: list[CellRecord] | None = None
) -> tuple[str, ...]:
    # Developer mode can pick a cellpy family directly; its own builder decides
    # the columns (and the basis), so the curated table does not apply (#97).
    if plot_type.startswith(FAMILY_PREFIX):
        family = plot_type[len(FAMILY_PREFIX) :]
        try:
            columns = family_columns(family, records)
        except Exception:  # noqa: BLE001 - fall back rather than break the plot
            log.warning("unknown cellpy plot family %r", family, exc_info=True)
            columns = ()
        if columns:
            return columns
        return ()

    s = _BASIS_SUFFIX.get(basis, "_gravimetric")
    table: dict[str, tuple[str, ...]] = {
        # CE on top (#81); pair with category_orders so Group avg cannot reorder.
        "capacity_ce": ("coulombic_efficiency", f"charge_capacity{s}", f"discharge_capacity{s}"),
        "capacity": (f"charge_capacity{s}", f"discharge_capacity{s}"),
        "charge_capacity": (f"charge_capacity{s}",),
        "discharge_capacity": (f"discharge_capacity{s}",),
        "coulombic_efficiency": ("coulombic_efficiency",),
        "cumulated_ce": ("cumulated_coulombic_efficiency",),
        "capacity_loss": (f"charge_capacity_loss{s}", f"discharge_capacity_loss{s}"),
        "end_voltages": ("potential_end_charge", "potential_end_discharge"),
        "internal_resistance": ("ir_charge", "ir_discharge"),
        "c_rate": ("charge_c_rate", "discharge_c_rate"),
    }
    return table.get(plot_type, table["capacity_ce"])


_PANEL_LABELS = {
    "charge_capacity": "Charge",
    "discharge_capacity": "Discharge",
    "coulombic_efficiency": "CE",
    "cumulated_coulombic_efficiency": "Cum. CE",
    "charge_capacity_loss": "Charge loss",
    "discharge_capacity_loss": "Discharge loss",
    "potential_end_charge": "EOC V",
    "potential_end_discharge": "EOD V",
    "ir_charge": "IR charge",
    "ir_discharge": "IR discharge",
    "charge_c_rate": "Charge C-rate",
    "discharge_c_rate": "Discharge C-rate",
}


def _panel_label(column: str) -> str:
    """Short UI label for a summary facet column id."""
    base = column
    for suffix in ("_gravimetric", "_areal"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return _PANEL_LABELS.get(base, base.replace("_", " "))


def _pretty_unit_text(label: str) -> str:
    """Normalize cellpy unit markup for plot titles (``cm**2`` → ``cm²``)."""
    return label.replace("**2", "²").replace("**3", "³")


def _capacity_mode_from_column(column: str) -> tuple[str, str | None]:
    """Strip basis suffix; return ``(base_id, mode|None)``."""
    for mode, suffix in (("gravimetric", "_gravimetric"), ("areal", "_areal")):
        if column.endswith(suffix):
            return column[: -len(suffix)], mode
    return column, None


#: Display names for summary columns fed to cellpy label builders (#38).
_SUMMARY_LABEL_SPECS: dict[str, tuple[str, str | None]] = {
    # base_id → (human name, physical_property or None for quantity_label-only)
    "charge_capacity": ("Charge capacity", "capacity"),
    "discharge_capacity": ("Discharge capacity", "capacity"),
    "charge_capacity_loss": ("Charge capacity loss", "capacity"),
    "discharge_capacity_loss": ("Discharge capacity loss", "capacity"),
    "coulombic_efficiency": ("Coulombic efficiency", None),
    "cumulated_coulombic_efficiency": ("Cumulated coulombic efficiency", None),
    "potential_end_charge": ("End-of-charge voltage", "voltage"),
    "potential_end_discharge": ("End-of-discharge voltage", "voltage"),
    "ir_charge": ("IR charge", "resistance"),
    "ir_discharge": ("IR discharge", "resistance"),
    "charge_c_rate": ("Charge C-rate", None),
    "discharge_c_rate": ("Discharge C-rate", None),
}


def _summary_column_axis_label(column: str) -> str:
    """One human axis title for a summary ``variable`` column id (#38)."""
    from cellpy.plotting import quantity_label, units_quantity_label

    base, mode = _capacity_mode_from_column(column)
    spec = _SUMMARY_LABEL_SPECS.get(base)
    if spec is None:
        try:
            from cellpy.plotting.collected import _pretty_variable_label

            return _pretty_unit_text(_pretty_variable_label(column))
        except Exception:  # noqa: BLE001 - cosmetics stay best-effort
            return base.replace("_", " ").title()

    name, physical = spec
    if physical == "capacity":
        # Absolute capacity columns have no suffix in this app.
        use_mode = mode or "absolute"
        return _pretty_unit_text(units_quantity_label(name, "capacity", mode=use_mode))
    if physical is not None:
        return _pretty_unit_text(units_quantity_label(name, physical, mode=mode))
    # CE / C-rate: no CellpyUnits physical_property yet (painpoint §18).
    unit = "%" if "efficiency" in base else "C"
    return quantity_label(name, unit)


def summary_y_label_mapper(columns: tuple[str, ...] | list[str]) -> dict[str, str]:
    """``variable →`` unit-bearing axis title via cellpy label builders (#38)."""
    return {col: _summary_column_axis_label(col) for col in columns}


def summary_panels_for(plot_type: str, basis: str) -> list[dict[str, str]]:
    """Panel descriptors (column id + short label) for summary y-range widgets."""
    return [
        {"id": col, "label": _panel_label(col)}
        for col in summary_columns_for(plot_type, basis)
    ]


def summary_columns(basis: str, charge: bool, discharge: bool, efficiency: bool) -> tuple[str, ...]:
    """Legacy charge/discharge/CE column selection (kept for tests)."""
    suffix = _BASIS_SUFFIX.get(basis, "_gravimetric")
    cols: list[str] = []
    if charge:
        cols.append(f"charge_capacity{suffix}")
    if discharge:
        cols.append(f"discharge_capacity{suffix}")
    if efficiency:
        cols.append("coulombic_efficiency")
    return tuple(cols) or (f"charge_capacity{suffix}",)


# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #


def summary_collection(
    records: list[CellRecord],
    *,
    columns: tuple[str, ...],
    group_it: bool = False,
    max_cycle: int | None = None,
    options=None,
):
    """Collect summaries, optionally under a family's own :class:`SummaryOptions`.

    ``options`` comes from :func:`family_summary_options` and already carries
    the family's ``columns``, CV split and transforms; the app only layers its
    own grouping and cycle cap on top (#868). Without it this is the plain
    column collect the curated plot types use.
    """
    if options is not None:
        return collect_summaries(
            _batch(records),
            options=options.replace(
                only_selected=False,  # records handed in are already the selected set
                group_it=group_it,
                max_cycle=max_cycle,
            ),
        )
    return collect_summaries(
        _batch(records),
        columns=columns,
        only_selected=False,
        group_it=group_it,
        max_cycle=max_cycle,
    )


def cycles_collection(
    records: list[CellRecord],
    *,
    cycles: tuple[int, ...],
    mode: str | None = None,
    method: str | None = None,
):
    opts = CurveOptions(cycles=cycles)
    changes = {}
    if mode:
        changes["mode"] = mode
    if method:
        changes["method"] = method
    if changes:
        opts = opts.replace(**changes)
    return collect_cycles(_batch(records), options=opts)


def ica_collection(
    records: list[CellRecord],
    *,
    cycles: tuple[int, ...],
    voltage_resolution: float | None = 0.005,
):
    """Collect ICA (dQ/dV) curves, both half-cycles (``direction`` column kept).

    Direction selection is delegated to cellpy: the plot passes ``direction`` to
    ``ica_plotter`` (#821), and exports use :func:`select_ica_direction` to match
    the chart. No app-side half-cycle filter on the collect step.
    """
    opts = IcaOptions(cycles=cycles, voltage_resolution=voltage_resolution)
    return collect_ica(_batch(records), options=opts)


def dva_collection(
    records: list[CellRecord],
    *,
    cycles: tuple[int, ...],
    voltage_resolution: float | None = None,
):
    """Collect DVA (dV/dQ) curves — the sibling of :func:`ica_collection`.

    cellpy 2.1.2a4 added ``collect_dva`` (#863); before that DVA was single-cell
    only and the app drove ``dva_plot`` directly. Going through a Collection
    means DVA gets the same grouping, multi-cell and polars export as ICA, and
    cellpy labels the ``both`` half-cycles itself (#862) — no app-side marking.
    """
    from cellpy.collect import collect_dva

    opts = IcaOptions(cycles=cycles, voltage_resolution=voltage_resolution)
    return collect_dva(_batch(records), options=opts)


def select_ica_direction(collection, direction: str):
    """Filter a collected ICA frame to one half-cycle for **export**.

    Mirrors what cellpy's ``ica_plotter`` draws (#821) so the exported data
    matches the chart. ``both`` (or an unknown value) keeps all directions.
    """
    want = (direction or "charge").lower()
    if want not in ("charge", "discharge"):
        return collection  # "both" -> keep both half-cycles
    data = getattr(collection, "data", None)
    if data is None or getattr(data, "height", 0) == 0:
        return collection
    if "direction" not in data.columns:
        log.warning("no 'direction' column in ICA frame - export filter skipped")
        return collection
    try:
        import polars as pl

        collection.data = data.filter(pl.col("direction").str.to_lowercase() == want)
    except Exception:  # noqa: BLE001 - export stays best-effort
        log.warning("could not filter ICA export by direction=%s", want, exc_info=True)
    return collection


# --------------------------------------------------------------------------- #
# Figures (Collection.plot -> cellpy.plotting -> plotly) + app restyle
# --------------------------------------------------------------------------- #


def is_grouped(collection) -> bool:
    """True when the collection carries averaged (mean/std) series."""
    flag = getattr(collection, "is_grouped", None)
    if flag is not None:
        return bool(flag)
    try:  # pre-2.1.1 fallback
        return "mean" in collection.data.columns
    except Exception:  # noqa: BLE001
        return False


def _inject_app_chrome(figure_theme: str, plot_kwargs: dict) -> dict:
    """Fold theme tokens into cellpy #801 knobs before ``collection.plot``."""
    tokens = _THEME_TOKENS.get(figure_theme, _THEME_TOKENS["light"])
    opts = dict(plot_kwargs)
    layout_updates = {
        "paper_bgcolor": tokens["paper_bgcolor"],
        "plot_bgcolor": tokens["plot_bgcolor"],
        "font": {
            "family": "Inter, Segoe UI, system-ui, sans-serif",
            "size": 12,
            "color": tokens["font_color"],
        },
        "autosize": True,
    }
    caller = opts.pop("layout_updates", None) or {}
    opts["layout_updates"] = {**layout_updates, **caller}
    opts.setdefault("height_per_panel", 250)
    # Extra chrome for axis labels / bottom margin so the last facet isn't clipped (#63).
    opts.setdefault("figure_border_height", 120)
    return opts


def _trace_axis_extent(
    fig,
    which: str,
    *,
    axis_id: str | None = None,
) -> tuple[float, float] | None:
    """Min/max over finite numeric samples on trace ``x`` or ``y``.

    When ``axis_id`` is set (e.g. ``\"y2\"``), only traces attached to that
    Plotly axis are included — needed for one-sided summary facet ranges.
    """
    import math

    axis_attr = "xaxis" if which == "x" else "yaxis"
    vals: list[float] = []
    for tr in fig.data:
        if axis_id is not None:
            tr_axis = str(getattr(tr, axis_attr, None) or which)
            if tr_axis != axis_id:
                continue
        arr = getattr(tr, which, None)
        if arr is None:
            continue
        try:
            iterable = list(arr)
        except TypeError:
            continue
        for raw in iterable:
            try:
                num = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isfinite(num):
                vals.append(num)
    if not vals:
        return None
    return min(vals), max(vals)


def _resolve_axis_range(
    fig,
    which: str,
    partial,
    *,
    axis_id: str | None = None,
) -> list[float] | None:
    """Turn ``[lo|None, hi|None]`` into a concrete ``[lo, hi]`` using data."""
    if not partial or len(partial) != 2:
        return None
    lo, hi = partial[0], partial[1]
    if lo is None and hi is None:
        return None
    if lo is None or hi is None:
        extent = _trace_axis_extent(fig, which, axis_id=axis_id)
        if extent is None:
            return None
        if lo is None:
            lo = extent[0]
        if hi is None:
            hi = extent[1]
    try:
        lo_f, hi_f = float(lo), float(hi)
    except (TypeError, ValueError):
        return None
    if lo_f < hi_f:
        return [lo_f, hi_f]
    return None


def _y_id_from_layout_key(layout_key: str) -> str:
    """``yaxis`` → ``y``, ``yaxis2`` → ``y2``."""
    if layout_key == "yaxis":
        return "y"
    if layout_key.startswith("yaxis"):
        return "y" + layout_key[len("yaxis") :]
    return "y"


def _apply_xy_ranges(fig, *, x_range=None, y_range=None) -> None:
    """Pin axes to ``[lo, hi]``; missing ends use the data extent."""
    resolved_x = _resolve_axis_range(fig, "x", x_range)
    if resolved_x:
        try:
            fig.update_xaxes(range=resolved_x, autorange=False)
        except Exception:  # noqa: BLE001
            log.warning("could not apply x_range=%r", x_range, exc_info=True)
    resolved_y = _resolve_axis_range(fig, "y", y_range)
    if resolved_y:
        try:
            fig.update_yaxes(range=resolved_y, autorange=False)
        except Exception:  # noqa: BLE001
            log.warning("could not apply y_range=%r", y_range, exc_info=True)


def curve_layout_kwargs(layout: str) -> dict:
    """Translate the app's curve *layout* into what cellpy actually expects.

    cellpy models the film view as a ``kind`` (a ``histogram2d``), not a layout;
    ``_LAYOUT_TO_METHOD`` has no ``"film"`` entry, so passing it as ``layout=``
    falls through to the line renderer and silently draws lines. Verified: same
    six ``scattergl`` traces as ``per_cell``, no error (CELLPY_PAINPOINTS §29).
    """
    if layout == "film":
        return {"kind": "film", "layout": "per_cell"}
    return {"layout": layout}


#: cellpy names the band edges of a spread plot; the mean line keeps the group.
_SPREAD_BOUND_PREFIXES = ("upper bound", "lower bound")


def _add_spread_hover(fig) -> None:
    """Give spread traces the hover the plain group-average plot already has (#40).

    ``spread_plot`` builds its traces with bare ``go.Scatter`` and never sets a
    hovertemplate, so turning Spread on drops hover entirely — group, variable,
    cycle and value all disappear. Everything needed is on the figure: the group
    is the mean trace's name, and the variable is the y-axis title the user is
    already reading. The band edge gives the spread itself, so the mean carries
    ``± std`` as customdata.

    Best-effort by design: hover is chrome, and a figure without it still draws.
    """
    try:
        import numpy as np

        for (_, yaxis), traces in _facet_traces(fig).items():
            variable = _axis_title(fig, yaxis)
            mean_tr = None
            for tr in traces:
                name = str(getattr(tr, "name", "") or "")
                if name.lower().startswith(_SPREAD_BOUND_PREFIXES):
                    # A band edge is not a data series; hovering it would report
                    # "mean+std" as though it were a measurement.
                    tr.hoverinfo = "skip"
                    if mean_tr is not None and name.lower().startswith("upper bound"):
                        _attach_spread(mean_tr, tr, variable, np)
                        mean_tr = None
                    continue
                mean_tr = tr
                tr.hovertemplate = _spread_hovertemplate(name, variable, spread=False)
    except Exception:  # noqa: BLE001 - hover is chrome, never break the chart
        log.warning("could not add hover to spread traces", exc_info=True)


def _spread_hovertemplate(group: str, variable: str, *, spread: bool) -> str:
    """Match the fields the non-averaged plot shows: series, variable, x, y."""
    value = "mean=%{y:.4g} ± %{customdata:.3g}" if spread else "mean=%{y:.4g}"
    return (
        f"group={group}<br>variable={variable}<br>cycle=%{{x}}<br>{value}<extra></extra>"
    )


def _attach_spread(mean_tr, upper_tr, variable: str, np) -> None:
    """Put the band half-width on the mean trace so hover can show ``± std``."""
    try:
        mean_y = np.asarray(mean_tr.y, dtype=float)
        upper_y = np.asarray(upper_tr.y, dtype=float)
        if mean_y.shape != upper_y.shape:
            return
        # A plain list, not the numpy array: plotly.io serialises arrays as a
        # base64 {dtype, bdata} blob that plotly.js does not decode for
        # customdata, so the tooltip would read "± NaN".
        mean_tr.customdata = [float(v) for v in np.abs(upper_y - mean_y)]
        mean_tr.hovertemplate = _spread_hovertemplate(
            str(mean_tr.name or ""), variable, spread=True
        )
    except Exception:  # noqa: BLE001 - keep the plain mean hover
        log.warning("could not attach spread to hover", exc_info=True)


def _facet_traces(fig) -> dict[tuple[str, str], list]:
    """Traces grouped by the subplot they live on, in figure order."""
    out: dict[tuple[str, str], list] = {}
    for tr in fig.data:
        key = (getattr(tr, "xaxis", None) or "x", getattr(tr, "yaxis", None) or "y")
        out.setdefault(key, []).append(tr)
    return out


def _axis_title(fig, yaxis: str) -> str:
    """The y-axis title for ``y``/``y2``/… — what names the facet on screen."""
    key = "yaxis" + yaxis[1:]
    axis = fig.layout[key] if key in fig.layout else None
    text = getattr(getattr(axis, "title", None), "text", None) or ""
    # Titles are pretty-printed and may wrap; hover wants one line.
    return text.replace("<br>", " ").strip()


def figure_json(
    collection,
    *,
    spread: bool = False,
    figure_theme: str = "light",
    color_scheme: str = "cellpy",
    **plot_kwargs,
) -> str:
    # spread (mean ± std band) only makes sense once actually group-averaged.
    if spread and not is_grouped(collection):
        spread = False
    try:
        x_range = plot_kwargs.pop("x_range", None)
        y_range = plot_kwargs.pop("y_range", None)
        # Per-facet summary limits (#60/#54); applied post-plot so they win over
        # any ``share_y`` axis matching cellpy set on the collection.
        y_ranges = plot_kwargs.pop("y_ranges", None)
        opts = _inject_app_chrome(figure_theme, plot_kwargs)
        # cellpy ≥2.1.2 honours share_y / match_axes on the collection itself,
        # incl. the group-avg + spread path (#816/#817), so no app re-link here.
        fig = collection.plot(spread=spread, **opts)
        if spread:
            _add_spread_hover(fig)
        _restyle(fig, figure_theme=figure_theme, color_scheme=color_scheme)
        if y_ranges:
            _apply_y_ranges(fig, y_ranges)
        else:
            _apply_xy_ranges(fig, x_range=x_range, y_range=y_range)
        return pio.to_json(fig)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(
            f"Could not render this plot ({exc}).", figure_theme=figure_theme
        )


def raw_figure_json(
    cell,
    *,
    plot_type: str = "voltage-current",
    max_points: int = 4000,
    figure_theme: str = "light",
    color_scheme: str = "cellpy",
    x_range=None,
    y_range=None,
) -> str:
    """Raw time-series traces for one cell, via cellpy's ``raw_plot``.

    cellpy 2.1.2 bounds the payload itself (``max_points``, #867) — 7.3 MB down
    to 0.2 MB for a demo cell — so the app no longer strides the traces. It does
    still say when the plot is downsampled, which ``raw_plot`` does not.
    """
    from cellpy.utils.plotutils import raw_plot

    try:
        fig = raw_plot(
            cell, plot_type=plot_type, backend="plotly", max_points=max_points
        )
        _restyle(fig, figure_theme=figure_theme, color_scheme=color_scheme)
        _apply_xy_ranges(fig, x_range=x_range, y_range=y_range)
        _note_downsampling(fig, cell)
        return pio.to_json(fig)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(
            f"Could not render raw data ({exc}).", figure_theme=figure_theme
        )


def cycle_info_figure_json(
    cell,
    *,
    cycles: tuple[int, ...],
    figure_theme: str = "light",
    color_scheme: str = "cellpy",
) -> str:
    """Raw traces annotated with step/cycle info, via cellpy's ``cycle_info_plot``.

    Bounded by the cycle selection rather than a point cap: one trace per cycle,
    ~1.5k points each, so there is nothing to thin.
    """
    from cellpy.utils.plotutils import cycle_info_plot

    try:
        # get_axes=True is what returns the *figure* on the plotly backend;
        # without it cycle_info_plot returns None.
        fig = cycle_info_plot(
            cell, cycle=list(cycles), backend="plotly", get_axes=True
        )
        if fig is None:
            return _empty_figure_json(
                "cellpy returned no cycle-info figure for this selection.",
                figure_theme=figure_theme,
            )
        _restyle(fig, figure_theme=figure_theme, color_scheme=color_scheme)
        return pio.to_json(fig)
    except Exception as exc:  # noqa: BLE001
        return _empty_figure_json(
            f"Could not render cycle info ({exc}).", figure_theme=figure_theme
        )


def _note_downsampling(fig, cell) -> None:
    """Say so when cellpy downsampled — a silently thinned plot is misleading.

    ``raw_plot`` honours ``max_points`` but draws no attention to it, so compare
    the longest trace with the raw frame and report the real numbers rather than
    assuming how cellpy picked the points.
    """
    try:
        shown = max(
            (0 if getattr(tr, "x", None) is None else len(tr.x) for tr in fig.data),
            default=0,
        )
        total = len(cell.data.raw)
        if not shown or shown >= total:
            return
        fig.add_annotation(
            text=f"showing {shown:,} of {total:,} points",
            xref="paper", yref="paper", x=1, y=1.04,
            xanchor="right", yanchor="bottom",
            showarrow=False, font=dict(size=10, color="#9aa5b1"),
        )
    except Exception:  # noqa: BLE001 - cosmetics stay best-effort
        log.warning("could not annotate downsampling", exc_info=True)


def _variable_axis_map(fig) -> dict[str, tuple[str, str]]:
    """Map facet ``variable`` → ``(xaxis_id, yaxis_id)`` from base traces.

    Prefer hover ``variable=…`` over y-axis title text: cellpy ≥2.1.1.post4
    pretty-prints axis titles (``Charge Capacity``) while hover keeps the
    column id (``charge_capacity_gravimetric``), which is what secondary
    figures still use for remapping.
    """
    out: dict[str, tuple[str, str]] = {}
    for tr in fig.data:
        var = _trace_variable(tr)
        if not var or var in out:
            continue
        x_id = getattr(tr, "xaxis", None) or "x"
        y_id = getattr(tr, "yaxis", None) or "y"
        out[var] = (str(x_id), str(y_id))
    return out


def _trace_variable(tr) -> str | None:
    """Pull ``variable=<name>`` from a PX hovertemplate, if present."""
    ht = getattr(tr, "hovertemplate", None) or ""
    for part in str(ht).split("<br>"):
        if part.startswith("variable="):
            return part.split("=", 1)[1].split("<", 1)[0].strip() or None
    return None


def _layout_key_for_y_id(y_id: str) -> str:
    """Plotly layout key for a trace ``yaxis`` id (``y`` → ``yaxis``, …)."""
    return "yaxis" if y_id == "y" else f"yaxis{y_id[1:]}"


def _apply_y_ranges(fig, y_ranges: dict) -> None:
    """Set per-facet ``[lo, hi]`` on the merged summary figure (#60 / #54).

    Prefer hover ``variable=…`` → axis map (same source as secondary remapping).
    Fall back to cellpy's facet/title resolver so spread bands (no hover
    ``variable=``) still match pretty axis titles.

    Either end of ``[lo, hi]`` may be null; the missing end is filled from that
    facet's trace extent (same idea as cycles/ICA ``x_range`` / ``y_range``).
    """
    if not y_ranges:
        return
    try:
        from cellpy.plotting.collected import _yaxis_key_for_variable
    except Exception:  # noqa: BLE001
        _yaxis_key_for_variable = None  # type: ignore[assignment]

    try:
        fig.update_yaxes(matches=None)
    except Exception:  # noqa: BLE001
        pass

    var_to_axes = _variable_axis_map(fig)
    for variable, y_range in y_ranges.items():
        if y_range is None:
            continue
        layout_key = None
        y_id = None
        axes = var_to_axes.get(variable)
        if axes:
            y_id = str(axes[1])
            layout_key = _layout_key_for_y_id(y_id)
        elif _yaxis_key_for_variable is not None:
            try:
                layout_key = _yaxis_key_for_variable(fig, variable)
            except Exception:  # noqa: BLE001
                layout_key = None
            if layout_key:
                y_id = _y_id_from_layout_key(layout_key)
        if not layout_key or layout_key not in fig.layout:
            log.warning(
                "y_ranges key %r did not match a summary facet axis; ignoring",
                variable,
            )
            continue
        resolved = _resolve_axis_range(fig, "y", y_range, axis_id=y_id)
        if not resolved:
            log.warning("ignoring invalid y_ranges[%r]=%r", variable, y_range)
            continue
        try:
            fig.layout[layout_key].update(range=resolved, autorange=False)
        except Exception:  # noqa: BLE001
            log.warning("could not apply y_ranges[%r]", variable, exc_info=True)


def _empty_figure_json(message: str, *, figure_theme: str = "light") -> str:
    import plotly.graph_objects as go

    tokens = _THEME_TOKENS.get(figure_theme, _THEME_TOKENS["light"])
    fig = go.Figure()
    _restyle(fig, figure_theme=figure_theme, color_scheme="cellpy")
    fig.add_annotation(
        text=message, showarrow=False, xref="paper", yref="paper",
        x=0.5, y=0.5, font=dict(size=14, color=tokens["annotation"]),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return pio.to_json(fig)


_LEGEND_NAME_LIMIT = 24
_FACET_STRIP_RIGHT_PAD = 72  # px reserved for right-side PX facet strip labels


def _truncate_label(name: str, limit: int = _LEGEND_NAME_LIMIT) -> str:
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


def _preserve_full_name_on_hover(tr, full_name: str) -> None:
    """Keep the full identity discoverable when display ``name`` is truncated.

    Plotly Express facet traces ship a ``hovertemplate`` that already embeds the
    full cell label as a literal prefix — leave that alone. When there is no
    template, fall back to ``hovertext`` (ignored by Plotly if a template exists).
    """
    template = getattr(tr, "hovertemplate", None)
    if template:
        return
    try:
        tr.hovertext = full_name
    except Exception:  # noqa: BLE001
        pass


def _shorten_legend(fig) -> int:
    """Truncate long legend-facing labels; return longest *displayed* length.

    Journal cells (especially merged runs) can have very long names that
    otherwise blow the legend up and squash the plot. Shortening always runs
    even when cosmetic layout updates fail later in :func:`_restyle`.
    """
    longest = 0
    for tr in fig.data:
        name = getattr(tr, "name", None)
        if name:
            if len(name) > _LEGEND_NAME_LIMIT:
                _preserve_full_name_on_hover(tr, name)
                tr.name = _truncate_label(name)
            longest = max(longest, len(tr.name))

        # PX sometimes puts the series identity on legendgroup instead of (or
        # as well as) name — keep the two consistent when group looks like a label.
        group = getattr(tr, "legendgroup", None)
        if isinstance(group, str) and len(group) > _LEGEND_NAME_LIMIT:
            # Numeric / short group ids ("1") are left alone; long label-like
            # groups get the same truncation as name.
            if not group.isdigit():
                tr.legendgroup = _truncate_label(group)
                longest = max(longest, len(tr.legendgroup))
    return longest


def _has_right_facet_strips(fig) -> bool:
    """True when PX facet annotations sit on the right edge (collide with legend)."""
    annotations = getattr(fig.layout, "annotations", None) or ()
    for ann in annotations:
        try:
            if float(getattr(ann, "x", 0) or 0) >= 0.9 and getattr(ann, "textangle", 0) in (90, -90):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _tidy_facet_annotations(fig) -> None:
    """Best-effort cleanup if a ``variable=…`` strip slipped past cellpy.

    cellpy ≥2.1.1.post4 pretty-prints facet labels by default (#801); keep this
    as a narrow fallback for older frames or edge paths.
    """
    annotations = getattr(fig.layout, "annotations", None) or ()
    for ann in annotations:
        text = getattr(ann, "text", None)
        if isinstance(text, str) and text.startswith("variable="):
            ann.text = text.split("=", 1)[1]


def _hex_to_rgba(color: str, alpha: float = 0.28) -> str:
    """Turn ``#RRGGBB`` into ``rgba(r,g,b,a)`` for translucent Plotly fills."""
    c = color.strip()
    if c.startswith("#") and len(c) == 7:
        r, g, b = (int(c[i : i + 2], 16) for i in (1, 3, 5))
        return f"rgba({r},{g},{b},{alpha})"
    if c.startswith("rgba("):
        return c
    if c.startswith("rgb("):
        return "rgba" + c[3:-1] + f",{alpha})"
    return color


def _apply_colorway(fig, color_scheme: str) -> None:
    """Cycle a discrete colorway across legend series (name / legendgroup)."""
    colors = COLOR_SCHEMES.get(color_scheme)
    if not colors:
        return
    series_key: dict[str, int] = {}
    for tr in fig.data:
        key = getattr(tr, "legendgroup", None) or getattr(tr, "name", None) or id(tr)
        key = str(key)
        if key not in series_key:
            series_key[key] = len(series_key)
        color = colors[series_key[key] % len(colors)]
        try:
            if getattr(tr, "line", None) is not None:
                tr.line.color = color
            if getattr(tr, "marker", None) is not None:
                tr.marker.color = color
            # Spread bands need alpha in fillcolor; tr.opacity is ignored for
            # fills or washes out the mean line when fill+line share a trace.
            fill = getattr(tr, "fill", None)
            if fill and fill != "none":
                tr.fillcolor = _hex_to_rgba(color, 0.28)
        except Exception:  # noqa: BLE001 - per-trace color is best-effort
            continue


def _restyle(
    fig,
    *,
    figure_theme: str = "light",
    color_scheme: str = "cellpy",
) -> None:
    """Post-plot polish: legend truncation, colorway, margins, soft axes.

    Paper/plot/font colors and panel height are preferably applied via cellpy
    ``layout_updates`` / ``height_per_panel`` (#801) in :func:`_inject_app_chrome`.
    This pass keeps app-owned legend/colorway behaviour and axis grid styling.
    """
    # Name truncation must not share fate with best-effort cosmetics.
    longest = _shorten_legend(fig)
    _apply_colorway(fig, color_scheme)
    tokens = _THEME_TOKENS.get(figure_theme, _THEME_TOKENS["light"])
    try:
        strip_pad = _FACET_STRIP_RIGHT_PAD if _has_right_facet_strips(fig) else 0
        legend_w = 40 + min(longest, _LEGEND_NAME_LIMIT) * 7 if longest else 28
        right = strip_pad + legend_w
        _tidy_facet_annotations(fig)
        # Re-assert theme tokens (covers empty figures that never hit #801 knobs).
        fig.update_layout(
            paper_bgcolor=tokens["paper_bgcolor"],
            plot_bgcolor=tokens["plot_bgcolor"],
            font=dict(
                family="Inter, Segoe UI, system-ui, sans-serif",
                size=12,
                color=tokens["font_color"],
            ),
            margin=dict(l=64, r=right, t=44, b=48),
            autosize=True,
            legend=dict(
                orientation="v", x=1.005, xanchor="left", y=1, yanchor="top",
                font=dict(size=10), bgcolor=tokens["legend_bg"],
            ),
        )
        fig.update_xaxes(
            showgrid=True, gridcolor=tokens["gridcolor"], zeroline=False,
            linecolor=tokens["linecolor"], mirror=False, ticks="outside",
            tickcolor=tokens["tickcolor"],
        )
        fig.update_yaxes(
            showgrid=True, gridcolor=tokens["gridcolor"], zeroline=False,
            linecolor=tokens["linecolor"], mirror=False, ticks="outside",
            tickcolor=tokens["tickcolor"],
        )
    except Exception:  # noqa: BLE001 - cosmetics stay best-effort; names already shortened
        log.warning("figure restyle cosmetics failed", exc_info=True)


# --------------------------------------------------------------------------- #
# Export (from the collected tidy frame — csv / xlsx / parquet / json)
# --------------------------------------------------------------------------- #

EXPORT_FORMATS = ("csv", "xlsx", "parquet", "json")
FIGURE_EXPORT_FORMATS = ("png", "svg", "pdf")

_MEDIA = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/octet-stream",
    "json": "application/json",
    "png": "image/png",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


def export_frame_bytes(data, fmt: str) -> tuple[bytes, str]:
    """Serialise a tidy polars frame in-memory. Returns (bytes, media_type)."""
    fmt = fmt.lower()
    buf = io.BytesIO()
    if fmt == "csv":
        buf.write(data.write_csv().encode("utf-8"))
    elif fmt == "parquet":
        data.write_parquet(buf)
    elif fmt == "json":
        buf.write(data.write_json().encode("utf-8"))
    elif fmt == "xlsx":
        data.to_pandas().to_excel(buf, index=False)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")
    return buf.getvalue(), _MEDIA[fmt]


def export_bytes(collection, fmt: str) -> tuple[bytes, str]:
    """Serialise a collection's tidy frame in-memory. Returns (bytes, media_type)."""
    return export_frame_bytes(collection.data, fmt)
