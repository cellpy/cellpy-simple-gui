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

import plotly.io as pio
from cellpy.collect import collect_cycles, collect_summaries, from_cells
from cellpy.collect.options import CurveOptions

from .library import CellRecord


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


def summary_columns(basis: str, charge: bool, discharge: bool, efficiency: bool) -> tuple[str, ...]:
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


def _empty_figure_json(message: str) -> str:
    import plotly.graph_objects as go

    fig = go.Figure()
    _restyle(fig)
    fig.add_annotation(text=message, showarrow=False, xref="paper", yref="paper",
                       x=0.5, y=0.5, font=dict(size=14, color="#7b8794"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return pio.to_json(fig)


def _restyle(fig) -> None:
    """Nudge cellpy's figure toward the app's look (white card, soft axes)."""
    try:
        layout = fig.layout.to_plotly_json()
        rows = max(1, len([k for k in layout if k.startswith("yaxis")]))
        fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=12, color="#1f2933"),
            margin=dict(l=64, r=28, t=44, b=48),
            height=min(250 * rows + 90, 1500),
            autosize=True,
        )
        fig.update_xaxes(showgrid=True, gridcolor="#eceff3", zeroline=False,
                         linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4")
        fig.update_yaxes(showgrid=True, gridcolor="#eceff3", zeroline=False,
                         linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4")
    except Exception:  # noqa: BLE001 - restyle is best-effort cosmetics
        pass


# --------------------------------------------------------------------------- #
# Export (from the collected tidy frame — csv / xlsx / parquet / json)
# --------------------------------------------------------------------------- #

EXPORT_FORMATS = ("csv", "xlsx", "parquet", "json")

_MEDIA = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/octet-stream",
    "json": "application/json",
}


def export_bytes(collection, fmt: str) -> tuple[bytes, str]:
    """Serialise a collection's tidy frame in-memory. Returns (bytes, media_type)."""
    fmt = fmt.lower()
    data = collection.data
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
