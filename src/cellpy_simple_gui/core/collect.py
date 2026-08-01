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
from collections import Counter

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


def summary_columns_for(plot_type: str, basis: str) -> tuple[str, ...]:
    s = _BASIS_SUFFIX.get(basis, "_gravimetric")
    table: dict[str, tuple[str, ...]] = {
        "capacity_ce": (f"charge_capacity{s}", f"discharge_capacity{s}", "coulombic_efficiency"),
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
):
    return collect_summaries(
        _batch(records),
        columns=columns,
        only_selected=False,  # records handed in are already the selected set
        group_it=group_it,
        max_cycle=max_cycle,
    )


def partition_by_group_size(
    records: list[CellRecord], *, min_size: int = 2
) -> tuple[list[CellRecord], list[CellRecord]]:
    """Split records into multi-member groups vs singletons (among *these* records).

    cellpy's ``group_it=True`` silently skips averaging when *any* group has
    fewer than ``min_size`` cells, so callers that want mixed behaviour must
    partition first (see :func:`summary_collections`).
    """
    sizes = Counter(r.group for r in records)
    multi = [r for r in records if sizes[r.group] >= min_size]
    solo = [r for r in records if sizes[r.group] < min_size]
    return multi, solo


def summary_collections(
    records: list[CellRecord],
    *,
    columns: tuple[str, ...],
    group_it: bool = False,
    max_cycle: int | None = None,
) -> list[tuple[object, bool]]:
    """Build one or two summary collections for plotting/export.

    When ``group_it`` is True, multi-member groups are averaged and singleton
    groups stay as ordinary per-cell series (so cellpy's all-or-nothing
    ``group_it`` guard cannot wipe out averaging for everyone). Each item is
    ``(collection, is_group_averaged)``.
    """
    if not records:
        return []
    if not group_it:
        return [(summary_collection(records, columns=columns, max_cycle=max_cycle), False)]

    multi, solo = partition_by_group_size(records)
    out: list[tuple[object, bool]] = []
    if multi:
        out.append(
            (
                summary_collection(
                    multi, columns=columns, group_it=True, max_cycle=max_cycle
                ),
                True,
            )
        )
    if solo:
        out.append(
            (
                summary_collection(
                    solo, columns=columns, group_it=False, max_cycle=max_cycle
                ),
                False,
            )
        )
    return out


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


def _filter_ica_by_direction(collection, direction: str):
    """Keep one half-cycle in a collected ICA frame.

    cellpy's ``ica_plotter`` documents ``direction`` but only applies
    ``_select_direction`` for ``method=="film"`` — default ``fig_pr_cell``
    line plots ignore it (CELLPY_PAINPOINTS §16 / issue #67). Filter here so
    Charge vs Discharge in the app actually differ.
    """
    data = getattr(collection, "data", None)
    if data is None or getattr(data, "height", 0) == 0:
        return collection
    if "direction" not in data.columns:
        log.warning(
            "no 'direction' column in ICA frame - direction filter skipped"
        )
        return collection
    want = (direction or "charge").lower()
    if want not in ("charge", "discharge"):
        want = "charge"
    try:
        import polars as pl

        filtered = data.filter(pl.col("direction").str.to_lowercase() == want)
        collection.data = filtered
    except Exception:  # noqa: BLE001 - plot path stays best-effort
        log.warning("could not filter ICA by direction=%s", want, exc_info=True)
    return collection


def ica_collection(
    records: list[CellRecord],
    *,
    cycles: tuple[int, ...],
    voltage_resolution: float | None = 0.005,
    direction: str = "charge",
):
    opts = IcaOptions(cycles=cycles, voltage_resolution=voltage_resolution)
    collection = collect_ica(_batch(records), options=opts)
    return _filter_ica_by_direction(collection, direction)


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


def _want_share_y(plot_kwargs: dict) -> bool:
    """True when the caller asked for shared facet y-scales (``share_y`` wins).

    Non-empty ``y_ranges`` always wins: fixed per-panel limits need unmatched
    axes (cellpy #804), and re-linking here would defeat them (#54).
    """
    if plot_kwargs.get("y_ranges"):
        return False
    if plot_kwargs.get("share_y") is not None:
        return bool(plot_kwargs["share_y"])
    if plot_kwargs.get("match_axes") is not None:
        return bool(plot_kwargs["match_axes"])
    return False


def _apply_share_y(fig, share: bool) -> None:
    """Link secondary facet y-axes to the primary when ``share`` is True.

    cellpy's non-spread summary path honours ``match_axes`` / ``share_y``; its
    ``spread_plot`` path (Group avg + Spread) does not. Re-apply here so the
    app checkbox stays honest for both.
    """
    if not share:
        return
    try:
        layout = fig.layout.to_plotly_json()
        for key in layout:
            if key.startswith("yaxis") and key != "yaxis":
                getattr(fig.layout, key).matches = "y"
    except Exception:  # noqa: BLE001 - cosmetics stay best-effort
        log.warning("could not apply shared y-axes", exc_info=True)


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
        opts = _inject_app_chrome(figure_theme, plot_kwargs)
        fig = collection.plot(spread=spread, **opts)
        _restyle(fig, figure_theme=figure_theme, color_scheme=color_scheme)
        _apply_share_y(fig, _want_share_y(plot_kwargs))
        return pio.to_json(fig)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(
            f"Could not render this plot ({exc}).", figure_theme=figure_theme
        )


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


def _remap_trace_axes(tr, var_to_axes: dict[str, tuple[str, str]]) -> None:
    """Align a secondary figure's facet ids with the base figure's variables."""
    var = _trace_variable(tr)
    if not var:
        return
    axes = var_to_axes.get(var)
    if not axes:
        return
    tr.xaxis, tr.yaxis = axes


def _layout_key_for_y_id(y_id: str) -> str:
    """Plotly layout key for a trace ``yaxis`` id (``y`` → ``yaxis``, …)."""
    return "yaxis" if y_id == "y" else f"yaxis{y_id[1:]}"


def _apply_y_ranges(fig, y_ranges: dict) -> None:
    """Set per-facet ``[lo, hi]`` on the merged summary figure (#60 / #54).

    Prefer hover ``variable=…`` → axis map (same source as secondary remapping).
    Fall back to cellpy's facet/title resolver so spread bands (no hover
    ``variable=``) still match pretty axis titles.
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
        try:
            lo, hi = float(y_range[0]), float(y_range[1])
        except (TypeError, ValueError, IndexError):
            log.warning("ignoring invalid y_ranges[%r]=%r", variable, y_range)
            continue
        layout_key = None
        axes = var_to_axes.get(variable)
        if axes:
            layout_key = _layout_key_for_y_id(axes[1])
        elif _yaxis_key_for_variable is not None:
            try:
                layout_key = _yaxis_key_for_variable(fig, variable)
            except Exception:  # noqa: BLE001
                layout_key = None
        if not layout_key or layout_key not in fig.layout:
            log.warning(
                "y_ranges key %r did not match a summary facet axis; ignoring",
                variable,
            )
            continue
        try:
            fig.layout[layout_key].update(range=[lo, hi], autorange=False)
        except Exception:  # noqa: BLE001
            log.warning("could not apply y_ranges[%r]", variable, exc_info=True)


def figures_json(
    parts: list[tuple[object, bool]],
    *,
    spread: bool = False,
    figure_theme: str = "light",
    color_scheme: str = "cellpy",
    **plot_kwargs,
) -> str:
    """Plot one or more collections and merge traces onto the first figure.

    ``parts`` is ``[(collection, is_group_averaged), ...]`` from
    :func:`summary_collections`. Spread bands apply only to averaged parts.

    Averaged (long) and per-cell (wide) collections can assign different Plotly
    subplot ids to the same ``variable``; traces from later parts are remapped
    onto the base figure's facet axes before merge.

    ``y_ranges`` is applied once on the merged base figure (#60) rather than
    forwarded into every ``collection.plot`` (secondary / spread parts can warn
    and no-op when a key does not match their local facet rows).
    """
    if not parts:
        return _empty_figure_json(
            "Select one or more cells to plot the cycle summary.",
            figure_theme=figure_theme,
        )

    try:
        y_ranges = plot_kwargs.get("y_ranges") or {}
        opts = _inject_app_chrome(figure_theme, plot_kwargs)
        opts.pop("y_ranges", None)
        base = None
        var_to_axes: dict[str, tuple[str, str]] = {}
        for collection, averaged in parts:
            use_spread = bool(spread and averaged and is_grouped(collection))
            fig = collection.plot(spread=use_spread, **opts)
            if base is None:
                base = fig
                var_to_axes = _variable_axis_map(base)
            else:
                for tr in fig.data:
                    _remap_trace_axes(tr, var_to_axes)
                    base.add_trace(tr)
        if base is None:
            return _empty_figure_json(
                "Select one or more cells to plot the cycle summary.",
                figure_theme=figure_theme,
            )
        _restyle(base, figure_theme=figure_theme, color_scheme=color_scheme)
        _apply_share_y(base, _want_share_y(plot_kwargs))
        _apply_y_ranges(base, y_ranges)
        return pio.to_json(base)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(
            f"Could not render this plot ({exc}).", figure_theme=figure_theme
        )


def combined_summary_frame(parts: list[tuple[object, bool]], columns: tuple[str, ...]):
    """Unify averaged + per-cell summary frames for a single export table.

    Averaged parts keep ``mean`` / ``std``. Singleton parts are melted to the
    same long shape with ``mean`` = value and ``std`` null, plus ``cell``.
    """
    import polars as pl

    frames = []
    for collection, averaged in parts:
        data = collection.data
        if data is None or data.height == 0:
            continue
        if averaged and is_grouped(collection):
            keep = [c for c in ("group", "group_label", "cycle_num", "variable", "mean", "std") if c in data.columns]
            frame = data.select(keep)
            if "cell" not in frame.columns:
                frame = frame.with_columns(pl.lit(None).cast(pl.Utf8).alias("cell"))
            frames.append(frame)
            continue
        id_vars = [c for c in ("cell", "group", "group_label", "cycle_num") if c in data.columns]
        value_vars = [c for c in columns if c in data.columns]
        if not value_vars:
            continue
        long = data.unpivot(
            index=id_vars, on=value_vars, variable_name="variable", value_name="mean"
        ).with_columns(pl.lit(None).cast(pl.Float64).alias("std"))
        frames.append(long)

    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal_relaxed")


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
        layout = fig.layout.to_plotly_json()
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
