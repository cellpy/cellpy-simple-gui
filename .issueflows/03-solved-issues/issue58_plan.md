# Issue #58 plan: plot side pane + top bar blend

## Goal

Declutter summary/cell top control rows by moving plot-local knobs into a
shared right-hand side pane next to each chart, and make the sticky top bar
blend with the app background.

## Constraints

- UI-only: HTML / CSS / light Alpine/JS. No API or `SummaryPlotSpec` changes.
- Y-range behaviour from #54 stays identical (same models / handlers).
- Side pane uses shell chrome (`--panel` / `--line`), not Plotly paper colors.
- No cell-explorer axis-range widgets; no collapsible pane.
- Prefer transparent top bar so the body’s radial gradient shows through
  (flatter `var(--bg)` alone would mismatch the gradient wash).

### Prior art

- `#54` y-range widgets in summary `.controls`
  (`index.html` template + `app.js` `yRanges` / `onYRangeChange`).
- `relayoutCharts()` already calls `Plotly.Plots.resize` on theme change and
  `window.resize` (`app.js`).
- `.chart-card` / `.controls` / `.topbar` tokens in `app.css`.
- Toolbox: none.

## Approach

1. **Top bar** — In `app.css`, set `.topbar` background to `transparent` (or
   inherit); remove `color-mix(...panel...)` and `backdrop-filter`. Keep the
   bottom border if it still helps separate brand from content; drop it only if
   it looks like a leftover strip after the blend.

2. **Shared chart row** — Add CSS:
   - `.chart-row { display: flex; gap: …; flex: 1; min-height: 0; align-items: stretch; }`
   - `.chart-row .chart-card { flex: 1; min-width: 0; }`
   - `.plot-sidepane` — narrow column (~180–220px), same panel border/radius/
     padding as `.controls` / `.panel`, stacked `.ctl` / `.yrange` vertically.
   Hide or collapse the pane when a tab has nothing to show (summary with zero
   panels is unlikely; still fine to render empty).

3. **Summary HTML** — Remove the y-range `x-for` from `.controls`. Wrap
   `#summaryChart`’s `.chart-card` in `.chart-row` + `<aside class="plot-sidepane">`
   containing a short heading (e.g. “Y ranges”) and the existing y-range
   widget markup.

4. **Cell explorer HTML** — Move cycles from/to, max curves, mode, method into
   a matching `.plot-sidepane` beside `#cellChart`. Leave cell select, theme,
   colors, export in `.controls`; leave `.cell-metrics` above the chart row.

5. **Resize** — After `plotSummary` / `plotCell` (and when switching tabs into a
   chart that already has data), call existing `relayoutCharts()` (optionally
   via `requestAnimationFrame`) so Plotly fills the narrower card. No new
   resize library.

6. **Design note** — Short entry under
   `.issueflows/04-designs-and-guides/` (e.g. `plot-sidepane.md`) recording the
   chrome choice + what lives in the pane vs top bar.

## Files to touch

| Path | Change |
|------|--------|
| `web/static/css/app.css` | Top bar blend; `.chart-row` / `.plot-sidepane` |
| `web/templates/index.html` | Restructure summary + cell chart areas |
| `web/static/js/app.js` | Ensure resize after plot / tab show |
| `.issueflows/04-designs-and-guides/plot-sidepane.md` | Terse layout decision |

## Test strategy

```bash
uv run --extra dev pytest
```

No new unit tests required (pure layout). Manual check with `csg-ui` / browser:
summary y-ranges still apply; both themes; tab switch + window resize reflow;
cell explorer controls still drive the plot.

## Open questions

None — issue spec is concrete enough to implement. Pane width ~200px unless
you prefer wider for long labels.
