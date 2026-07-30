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
from cellpy.collect import collect_cycles, collect_summaries, from_cells
from cellpy.collect.options import CurveOptions

from .library import CellRecord

log = logging.getLogger(__name__)


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


def figure_json(collection, *, spread: bool = False, **plot_kwargs) -> str:
    # spread (mean ± std band) only makes sense once actually group-averaged.
    if spread and not is_grouped(collection):
        spread = False
    try:
        fig = collection.plot(spread=spread, **plot_kwargs)
        _restyle(fig)
        return pio.to_json(fig)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(f"Could not render this plot ({exc}).")


def figures_json(
    parts: list[tuple[object, bool]],
    *,
    spread: bool = False,
    **plot_kwargs,
) -> str:
    """Plot one or more collections and merge traces onto the first figure.

    ``parts`` is ``[(collection, is_group_averaged), ...]`` from
    :func:`summary_collections`. Spread bands apply only to averaged parts.
    """
    if not parts:
        return _empty_figure_json("Select one or more cells to plot the cycle summary.")

    try:
        base = None
        for collection, averaged in parts:
            use_spread = bool(spread and averaged and is_grouped(collection))
            fig = collection.plot(spread=use_spread, **plot_kwargs)
            if base is None:
                base = fig
            else:
                for tr in fig.data:
                    base.add_trace(tr)
        if base is None:
            return _empty_figure_json("Select one or more cells to plot the cycle summary.")
        _restyle(base)
        return pio.to_json(base)
    except Exception as exc:  # noqa: BLE001 - never leave the user with a broken chart
        return _empty_figure_json(f"Could not render this plot ({exc}).")


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


def _empty_figure_json(message: str) -> str:
    import plotly.graph_objects as go

    fig = go.Figure()
    _restyle(fig)
    fig.add_annotation(text=message, showarrow=False, xref="paper", yref="paper",
                       x=0.5, y=0.5, font=dict(size=14, color="#7b8794"))
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
    """Shorten ``variable=…`` facet strip text so it fights the legend less."""
    annotations = getattr(fig.layout, "annotations", None) or ()
    for ann in annotations:
        text = getattr(ann, "text", None)
        if isinstance(text, str) and text.startswith("variable="):
            ann.text = text.split("=", 1)[1]


def _restyle(fig) -> None:
    """Nudge cellpy's figure toward the app's look (white card, soft axes,
    a compact right-hand legend that survives long cell names)."""
    # Name truncation must not share fate with best-effort cosmetics.
    longest = _shorten_legend(fig)
    try:
        layout = fig.layout.to_plotly_json()
        rows = max(1, len([k for k in layout if k.startswith("yaxis")]))
        strip_pad = _FACET_STRIP_RIGHT_PAD if _has_right_facet_strips(fig) else 0
        legend_w = 40 + min(longest, _LEGEND_NAME_LIMIT) * 7 if longest else 28
        right = strip_pad + legend_w
        _tidy_facet_annotations(fig)
        fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=12, color="#1f2933"),
            margin=dict(l=64, r=right, t=44, b=48),
            height=min(250 * rows + 90, 1500),
            autosize=True,
            legend=dict(
                orientation="v", x=1.005, xanchor="left", y=1, yanchor="top",
                font=dict(size=10), bgcolor="rgba(255,255,255,0.6)",
            ),
        )
        fig.update_xaxes(showgrid=True, gridcolor="#eceff3", zeroline=False,
                         linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4")
        fig.update_yaxes(showgrid=True, gridcolor="#eceff3", zeroline=False,
                         linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4")
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
