# Issue #2 status

- [ ] Done

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
- `uv run pytest`: all passed.

## Remaining work

- `/iflow-close` (finalize PR / ship).

PR: https://github.com/cellpy/cellpy-simple-gui/pull/11 (#11, draft)
