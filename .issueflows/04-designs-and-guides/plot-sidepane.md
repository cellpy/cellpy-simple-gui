# Plot side pane (#58)

## Context

Summary y-range widgets (#54) crowded the top controls row. Both plot tabs
also left unused width beside the Plotly card.

## Decision

- Shared `.chart-row` + `.plot-sidepane` (~200px) beside each chart.
- Pane chrome matches the app shell (`--panel` / `--line`), not figure paper.
- **Summary pane:** per-panel y-range min/max only.
- **Cell explorer pane:** cycles from/to, max curves, mode, method.
- Top bar stays for global plot/appearance/export controls.
- Sticky `.topbar` is transparent so the body gradient shows through.
- `.plot-sidepane` is `position: sticky` while `.main` scrolls (#63).

## Alternatives considered

- Collapsible pane — deferred; always-on is simpler for MVP.
- Cell-explorer axis ranges — out of scope until requested.
