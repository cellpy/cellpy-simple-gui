"""Build Plotly figures from cell data.

We construct our own figures (rather than leaning on cellpy's batch plotting)
so the look is fully under our control and stable across cellpy versions. Each
function returns a Plotly figure JSON *string* (numpy-safe) ready to hand to
Plotly.js in the browser or to kaleido for static export.
"""

from __future__ import annotations

from typing import Iterable

import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from . import cellpy_adapter as adapter
from .library import CellRecord
from .models import CAPACITY_UNITS, CyclesPlotSpec, SummaryPlotSpec

# --------------------------------------------------------------------------- #
# Shared theme
# --------------------------------------------------------------------------- #

FONT = dict(family="Inter, Segoe UI, system-ui, sans-serif", size=13, color="#1f2933")
GRID = "#eceff3"
AXIS_LINE = "#c7ccd4"

_BASE_LAYOUT = dict(
    font=FONT,
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=70, r=24, t=56, b=56),
    hovermode="closest",
    legend=dict(
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="#e3e7ec",
        borderwidth=1,
        font=dict(size=12),
    ),
    colorway=[
        "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
        "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
    ],
)


def _style_axes(fig: go.Figure) -> None:
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID, zeroline=False,
        linecolor=AXIS_LINE, ticks="outside", tickcolor=AXIS_LINE,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, zeroline=False,
        linecolor=AXIS_LINE, ticks="outside", tickcolor=AXIS_LINE,
    )


def _to_json(fig: go.Figure) -> str:
    return pio.to_json(fig)


def _capacity_column(mode: str, direction: str) -> str:
    if mode == "gravimetric":
        return f"{direction}_capacity_gravimetric"
    if mode == "areal":
        return f"{direction}_capacity_areal"
    return f"{direction}_capacity"


def _empty_figure(message: str) -> str:
    fig = go.Figure()
    fig.update_layout(**_BASE_LAYOUT)
    fig.add_annotation(
        text=message, showarrow=False,
        font=dict(size=15, color="#7b8794"),
        xref="paper", yref="paper", x=0.5, y=0.5,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _to_json(fig)


# --------------------------------------------------------------------------- #
# Summary figure (multi-cell, per-cycle)
# --------------------------------------------------------------------------- #


def summary_figure(records: list[CellRecord], spec: SummaryPlotSpec) -> str:
    if not records:
        return _empty_figure("Select one or more cells to plot the cycle summary.")

    column = _capacity_column(spec.mode, spec.direction)
    unit = CAPACITY_UNITS[spec.mode]
    show_eff = spec.show_efficiency

    rows = 2 if show_eff else 1
    row_heights = [0.68, 0.32] if show_eff else [1.0]
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=row_heights,
    )

    mode = "lines+markers" if spec.markers else "lines"
    seen_groups: set[int] = set()

    for rec in records:
        try:
            df = adapter.summary_frame(rec.cell)
        except Exception:  # noqa: BLE001
            continue
        if column not in df.columns or "cycle_num" not in df.columns:
            continue

        color = rec.color() if spec.group_colors else None
        # When colouring by group, only show one legend entry per group.
        show_legend = True
        if spec.group_colors:
            show_legend = rec.group not in seen_groups
            seen_groups.add(rec.group)
        legend_name = f"grp {rec.group}" if spec.group_colors else (rec.label or rec.name)

        fig.add_trace(
            go.Scatter(
                x=df["cycle_num"], y=df[column],
                name=legend_name, legendgroup=str(rec.group),
                showlegend=show_legend, mode=mode,
                line=dict(color=color, width=2),
                marker=dict(size=5, line=dict(width=0)),
                customdata=[rec.label or rec.name] * len(df),
                hovertemplate=(
                    "<b>%{customdata}</b><br>cycle %{x}<br>"
                    f"{spec.direction} cap %{{y:.1f}} {unit}<extra></extra>"
                ),
            ),
            row=1, col=1,
        )

        if show_eff and "coulombic_efficiency" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["cycle_num"], y=df["coulombic_efficiency"],
                    name=legend_name, legendgroup=str(rec.group),
                    showlegend=False, mode=mode,
                    line=dict(color=color, width=1.5),
                    marker=dict(size=4),
                    customdata=[rec.label or rec.name] * len(df),
                    hovertemplate=(
                        "<b>%{customdata}</b><br>cycle %{x}<br>"
                        "CE %{y:.2f} %<extra></extra>"
                    ),
                ),
                row=2, col=1,
            )

    fig.update_layout(**_BASE_LAYOUT)
    fig.update_layout(
        title=dict(text=spec.title, x=0.01, xanchor="left", font=dict(size=17)),
        legend=dict(**_BASE_LAYOUT["legend"], orientation="v", x=1.01, y=1.0),
    )
    _style_axes(fig)
    cap_axis = f"{spec.direction.capitalize()} capacity ({unit})"
    if show_eff:
        fig.update_yaxes(title_text=cap_axis, row=1, col=1)
        fig.update_yaxes(title_text="CE (%)", row=2, col=1)
        fig.update_xaxes(title_text="Cycle number", row=2, col=1)
    else:
        fig.update_yaxes(title_text=cap_axis, row=1, col=1)
        fig.update_xaxes(title_text="Cycle number", row=1, col=1)
    return _to_json(fig)


# --------------------------------------------------------------------------- #
# Per-cell voltage-capacity cycles figure
# --------------------------------------------------------------------------- #


def cycles_figure(rec: CellRecord, spec: CyclesPlotSpec) -> str:
    cycles = sorted(set(spec.cycles))
    if not cycles:
        return _empty_figure("Pick one or more cycles to plot the voltage curves.")

    unit = CAPACITY_UNITS[spec.mode]
    fig = go.Figure()

    n = len(cycles)
    for i, cyc in enumerate(cycles):
        try:
            df = adapter.capacity_curve(rec.cell, cyc, mode=spec.mode, method=spec.method)
        except Exception:  # noqa: BLE001
            continue
        if df.empty:
            continue
        # Sequential blue->red shade so cycle progression is readable.
        t = i / max(n - 1, 1)
        color = _shade(t)
        fig.add_trace(
            go.Scatter(
                x=df["capacity"], y=df["potential"],
                name=f"cycle {cyc}", mode="lines",
                line=dict(color=color, width=1.8),
                hovertemplate=(
                    f"cycle {cyc}<br>cap %{{x:.1f}} {unit}<br>"
                    "V %{y:.3f}<extra></extra>"
                ),
            )
        )

    title = spec.title or f"Voltage curves — {rec.label or rec.name}"
    fig.update_layout(**_BASE_LAYOUT)
    fig.update_layout(title=dict(text=title, x=0.01, xanchor="left", font=dict(size=17)))
    _style_axes(fig)
    fig.update_xaxes(title_text=f"Capacity ({unit})")
    fig.update_yaxes(title_text="Cell potential (V)")
    return _to_json(fig)


def _shade(t: float) -> str:
    """Interpolate blue -> red for a sequential cycle colour."""
    a = (0x4C, 0x78, 0xA8)
    b = (0xE4, 0x57, 0x56)
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    bl = int(a[2] + (b[2] - a[2]) * t)
    return f"rgb({r},{g},{bl})"
