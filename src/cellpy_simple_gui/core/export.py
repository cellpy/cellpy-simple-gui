"""Export helpers: summary/cycle data to CSV, and figures to static images."""

from __future__ import annotations

import io

import pandas as pd

from . import cellpy_adapter as adapter
from .library import CellRecord
from .models import CyclesPlotSpec, SummaryPlotSpec, CAPACITY_UNITS
from .plotting import _capacity_column


def summary_csv(records: list[CellRecord], spec: SummaryPlotSpec) -> bytes:
    """Wide CSV: one column block per selected cell."""
    column = _capacity_column(spec.mode, spec.direction)
    frames: list[pd.DataFrame] = []
    for rec in records:
        try:
            df = adapter.summary_frame(rec.cell)
        except Exception:  # noqa: BLE001
            continue
        if column not in df.columns:
            continue
        name = rec.label or rec.name
        sub = pd.DataFrame({"cycle": df["cycle_num"]})
        sub[f"{name}::{spec.direction}_capacity_{spec.mode}"] = df[column].values
        if "coulombic_efficiency" in df.columns:
            sub[f"{name}::coulombic_efficiency"] = df["coulombic_efficiency"].values
        frames.append(sub.set_index("cycle"))
    if not frames:
        return b"cycle\n"
    out = pd.concat(frames, axis=1)
    buf = io.StringIO()
    out.to_csv(buf)
    return buf.getvalue().encode("utf-8")


def cycles_csv(rec: CellRecord, spec: CyclesPlotSpec) -> bytes:
    """Long CSV of voltage-capacity points for the selected cycles."""
    parts: list[pd.DataFrame] = []
    for cyc in sorted(set(spec.cycles)):
        try:
            df = adapter.capacity_curve(rec.cell, cyc, mode=spec.mode, method=spec.method)
        except Exception:  # noqa: BLE001
            continue
        if df.empty:
            continue
        df = df.copy()
        df.insert(0, "cycle", cyc)
        parts.append(df)
    if not parts:
        return b"cycle,capacity,potential\n"
    out = pd.concat(parts, ignore_index=True)
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def figure_image(figure_json: str, fmt: str = "png") -> bytes:
    """Render a Plotly figure JSON to a static image via kaleido (optional dep)."""
    import plotly.io as pio

    fig = pio.from_json(figure_json)
    return fig.to_image(format=fmt, scale=2, width=1100, height=650)
