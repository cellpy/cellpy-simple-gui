# Plot side pane (#58, #55)

## Context

Summary y-range widgets (#54) crowded the top controls row. Both plot tabs
also left unused width beside the Plotly card. #55 added a multi-cell Cycles
collector as a third tab.

## Decision

- Shared `.chart-row` + `.plot-sidepane` (~200px) beside each chart.
- Pane chrome matches the app shell (`--panel` / `--line`), not figure paper.
- **Summary pane:** per-panel y-range min/max only.
- **Cycles pane (collector):** layout (`per_cell` / `per_cycle`), cycles
  from/to, max curves, mode, method; optional Capacity x / Voltage y ranges
  (same `x_range` / `y_range` on `CyclesPlotSpec` as Cell explorer — needed so
  kaleido exports match zoom, since interactive Plotly zoom is not in the
  export spec). Plots **selected** sidebar cells.
- **Cell explorer pane:** plot kind (`Voltage curves` / `dQ/dV`), cycles
  from/to, max curves; mode/method when curves; V resolution + direction when
  dQ/dV (one cell; curves layout stays `per_cell`); optional x/y range
  min–max (either end blank = fill from data extent). Labels switch with plot kind (capacity/voltage
  vs voltage/dQ/dV). Spec fields `x_range` / `y_range` on
  `CyclesPlotSpec` / `IcaPlotSpec` so exports match the on-screen figure.
- Top bar stays for global plot/appearance/export controls.
- Sticky `.topbar` is transparent so the body gradient shows through.
- `.plot-sidepane` is `position: sticky` while `.main` scrolls (#63).
- Tab order: Cycle summary | Cycles | Cell explorer.

## Alternatives considered

- Collapsible pane — deferred; always-on is simpler for MVP.
- Cell-explorer axis ranges — shipped when requested (client-only Plotly
  relayout rejected so kaleido exports stay in sync).
- Folding Cycles into Cycle summary or Cell explorer — rejected (#55); summary
  is dense/summary-series; explorer stays single-cell.
