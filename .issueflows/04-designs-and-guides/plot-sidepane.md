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
  from/to, max curves, mode, method. Plots **selected** sidebar cells.
- **Cell explorer pane:** cycles from/to, max curves, mode, method (one cell;
  layout stays `per_cell`).
- Top bar stays for global plot/appearance/export controls.
- Sticky `.topbar` is transparent so the body gradient shows through.
- `.plot-sidepane` is `position: sticky` while `.main` scrolls (#63).
- Tab order: Cycle summary | Cycles | Cell explorer.

## Alternatives considered

- Collapsible pane — deferred; always-on is simpler for MVP.
- Cell-explorer axis ranges — out of scope until requested.
- Folding Cycles into Cycle summary or Cell explorer — rejected (#55); summary
  is dense/summary-series; explorer stays single-cell.
