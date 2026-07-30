# Issue #2 status

- [x] Done

## What's done

- Plan accepted (`share_y=False` default → cellpy `match_axes`; defer fixed
  per-panel limits to cellpy #804).
- `SummaryPlotSpec.share_y` + `plotting.summary_figure` forwards
  `match_axes=spec.share_y`.
- Summary UI: **Share y-scale** checkbox (`app.js` / `index.html`).
- Regression tests: independent default, shared matches, CE≈1e6 outlier on
  figure-json path (binary `y` decode + facet-strip mapping).
- Design note: `.issueflows/04-designs-and-guides/summary-independent-y-scales.md`.
- `CELLPY_PAINPOINTS.md` §12 → cellpy #804.
- `uv run pytest`: 44 passed.
- No `HISTORY.md` at repo root — changelog update skipped.
- Closed via `/iflow-close`; issue-flow files moved to `03-solved-issues/`.

## Remaining work

None.

PR: https://github.com/cellpy/cellpy-simple-gui/pull/11 (#11)
