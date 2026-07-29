"""Bridge the in-memory library into cellpy's own collect / plot / export stack.

Rather than re-implementing summaries, grouping and multi-cell plotting, we hand
our loaded cells to cellpy 2.1's :mod:`cellpy.collect` subsystem and let it do
the work — so grouping, spread, per-cell cycle isolation, the curated plot
families and multi-format export all come "for free" and stay consistent with
cellpy itself.

The one glue piece is a tiny *batch shim*: ``cellpy.collect`` only needs an
object exposing ``.cells`` (``{label: CellpyCell}``) and ``.journal.pages`` (a
polars frame with ``filename`` / ``group`` / ``selected`` …). We build that from
the library's records; no files or real Batch object required.
"""

from __future__ import annotations

import io
from typing import Any, Iterable

import plotly.io as pio
import polars as pl

from cellpy.batch.journal import FILENAME
from cellpy.collect import collect_cycles, collect_summaries

from .library import CellRecord

# Column that carries the human-facing series name into cellpy's collection.
_DISPLAY = "label"


# --------------------------------------------------------------------------- #
# Batch shim
# --------------------------------------------------------------------------- #


class _JournalShim:
    def __init__(self, pages: pl.DataFrame, name: str) -> None:
        self.pages = pages
        self.name = name


class _BatchShim:
    """Minimal duck-typed batch that ``cellpy.collect`` is happy to consume."""

    def __init__(self, records: list[CellRecord], name: str = "cellpy-simple-gui") -> None:
        self.cells: dict[str, Any] = {}
        rows: list[dict[str, Any]] = []
        seen: dict[str, int] = {}
        for rec in records:
            # keys must be unique across cells; disambiguate duplicate labels
            key = rec.label or rec.name or rec.id
            if key in seen:
                seen[key] += 1
                key = f"{key} ({seen[key]})"
            else:
                seen[key] = 1
            self.cells[key] = rec.cell
            rows.append(
                {
                    FILENAME: key,
                    "group": rec.group,
                    "sub_group": 1,
                    "group_label": f"group {rec.group}",
                    _DISPLAY: rec.label or rec.name,
                    "selected": 1 if rec.selected else 0,
                }
            )
        pages = pl.DataFrame(rows) if rows else pl.DataFrame(
            schema={FILENAME: pl.Utf8, "group": pl.Int64, "sub_group": pl.Int64,
                    "group_label": pl.Utf8, _DISPLAY: pl.Utf8, "selected": pl.Int64}
        )
        self.journal = _JournalShim(pages, name)


def _shim(records: Iterable[CellRecord]) -> _BatchShim:
    return _BatchShim(list(records))


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
        _shim(records),
        columns=columns,
        only_selected=False,  # the library already hands us the selected set
        group_it=group_it,
        max_cycle=max_cycle,
    )


def cycles_collection(records: list[CellRecord], *, cycles: tuple[int, ...]):
    return collect_cycles(_shim(records), cycles=cycles)


# --------------------------------------------------------------------------- #
# Figures (Collection.plot -> cellpy.plotting -> plotly) + app restyle
# --------------------------------------------------------------------------- #


def figure_json(collection, *, spread: bool = False, **plot_kwargs) -> str:
    # ``spread`` (mean ± std band) is only meaningful once the collection has
    # actually been group-averaged — cellpy declines to average groups with a
    # single cell, leaving a wide frame with no ``mean``/``std`` columns.
    if spread and not is_grouped(collection):
        spread = False
    # Try the requested rendering, then degrade gracefully (spread first, then
    # a plain render) so a rough edge in one cellpy plotting path never leaves
    # the user staring at a broken chart.
    attempts = [spread, False] if spread else [False]
    last_err: Exception | None = None
    for attempt in attempts:
        try:
            fig = collection.plot(spread=attempt, **plot_kwargs)
            _restyle(fig)
            return pio.to_json(fig)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    return _empty_figure_json(f"Could not render this plot ({last_err}).")


def _empty_figure_json(message: str) -> str:
    import plotly.graph_objects as go

    fig = go.Figure()
    _restyle(fig)
    fig.add_annotation(text=message, showarrow=False, xref="paper", yref="paper",
                       x=0.5, y=0.5, font=dict(size=14, color="#7b8794"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return pio.to_json(fig)


def is_grouped(collection) -> bool:
    """True when the collection carries averaged (mean/std) series."""
    try:
        return "mean" in collection.data.columns
    except Exception:  # noqa: BLE001
        return False


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
        fig.update_xaxes(
            showgrid=True, gridcolor="#eceff3", zeroline=False,
            linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4",
        )
        fig.update_yaxes(
            showgrid=True, gridcolor="#eceff3", zeroline=False,
            linecolor="#c7ccd4", mirror=False, ticks="outside", tickcolor="#c7ccd4",
        )
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
    """Serialise a collection's tidy frame. Returns (bytes, media_type)."""
    fmt = fmt.lower()
    data: pl.DataFrame = collection.data
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
