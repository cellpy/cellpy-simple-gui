# Issue #2: Allow independent y-limits on multi-panel summary plots

Source: https://github.com/cellpy/cellpy-simple-gui/issues/2

## Original issue text

## Problem / context

Summary plots that facet several variables (e.g. Capacity + coulombic efficiency) share one y-scale across panels. A CE outlier (order of 1e6) flattens capacity (and other) panels so the useful signal is unreadable.

The app builds figures via `Collection.plot()` → cellpy `collected_plot` / `summary_plotter` → `_cycles_plotter`, which defaults to `match_axes=True`. The app does not expose `match_axes`, nor any per-panel y-range controls (`SummaryPlotSpec` has no axis-limit fields).

**Companion (cellpy):** https://github.com/jepegit/cellpy/issues/804

## Spec

1. **Independent auto-scale (app, likely ready now):** default multi-variable summary figures to independent y-axes (forward `match_axes=False`, or equivalent), or expose a clear UI toggle (e.g. “Share y-scale”) with independent as the sensible default when CE (or mixed units/scales) is present.
2. **Per-panel limits (app + cellpy):** let the user set min/max per summary panel/variable (at least for CE; ideally for each faceted variable). Wire through `SummaryPlotSpec` → plot API → cellpy. If cellpy cannot take per-panel ranges on this path, document the gap and track it on the companion cellpy issue (link from this issue).
3. **Regression test:** multi-panel summary with an extreme CE value must not force capacity panels onto a million-scale axis when independent scaling (or an explicit CE limit) is active.

## Acceptance criteria

- [ ] Capacity + CE (and similar multi-panel summaries) remain readable when CE has large outliers.
- [ ] User can choose shared vs independent y-scales (or independent is default and shared is optional — decide in plan).
- [ ] User can set individual y-limits for at least the CE panel when cellpy supports it; otherwise the companion cellpy issue is filed and linked, and the app ships independent auto-scale without pretending fixed limits work.
- [ ] Short/normal-range data still looks fine (no huge empty margins from bad defaults).
- [ ] Automated test covers the outlier / independent-scale case on the figure-json path.

## Out of scope

- Full interactive Plotly axis-editing chrome beyond what’s needed for limits / share toggle.
- Changing cellpy’s global defaults for all callers (that’s the companion issue).
- Legend long-name layout (#1).
