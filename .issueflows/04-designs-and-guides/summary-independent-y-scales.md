# Summary plot independent y-scales (#2)

## Context

Multi-variable collected summaries (e.g. Capacity + CE) facet one row per
variable. cellpy’s `_cycles_plotter` defaults to `match_axes=True`, so a CE
outlier (~1e6) flattens capacity panels.

## Decision

- App default: **independent** auto-scale. `SummaryPlotSpec.share_y=False`
  forwards as `match_axes=False` through `plotting.summary_figure` →
  `collect.figure_json`.
- UI: optional **Share y-scale** checkbox for users who want matched panels.
- **Per-panel fixed y-limits** are not implemented in the app yet — cellpy’s
  collected summary path has no reliable per-facet-row range API. Tracked
  upstream: https://github.com/jepegit/cellpy/issues/804

## Alternatives considered

- Shared-by-default + opt-in independent — rejected; mixed-unit panels are the
  common Capacity+CE case and should stay readable without a toggle.
- App-side post-restyle CE min/max hack — deferred until #804; avoids pretending
  fixed limits work end-to-end.
