# Summary plot y-scales (#2, #54)

## Context

Multi-variable collected summaries (e.g. Capacity + CE) facet one row per
variable. cellpy’s `_cycles_plotter` historically defaulted to
`match_axes=True`, so a CE outlier (~1e6) flattened capacity panels.

## Decision

- App default: **independent** auto-scale. `SummaryPlotSpec.share_y=False`
  forwards as `match_axes=False` through `plotting.summary_figure` →
  `collect.figure_json`.
- UI: optional **Share y-scale** checkbox for users who want matched panels.
  After group-avg + spread, the app still re-applies `matches` (#47 / cellpy
  spread gap).
- **Per-panel fixed y-limits** (#54): `SummaryPlotSpec.y_ranges` maps summary
  column id → `[lo, hi]` and is forwarded as cellpy `y_ranges` (#804, since
  2.1.1.post2). Omitted keys stay autorange. Non-empty `y_ranges` forces
  independent axes; the app suppresses `_apply_share_y` and the UI disables
  Share y-scale while any range is set.
- UI widgets: min/max number inputs per current plot-type panel (session-only;
  both ends required).

## Alternatives considered

- Shared-by-default + opt-in independent — rejected; mixed-unit panels are the
  common Capacity+CE case and should stay readable without a toggle.
- App-side post-restyle CE min/max hack — superseded by cellpy #804 forwarding.
