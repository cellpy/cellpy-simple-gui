# Issue #1 status

- [x] Done

## What's done

- Diagnosed long-name summary figures: `trace.name` holds the label; PX
  `hovertemplate` already embeds the full name; right-side facet strips share
  the legend margin; bare `except` could skip shortening with cosmetics.
- Hardened `collect._shorten_legend` / `_restyle`: shorten always runs first;
  truncate long non-numeric `legendgroup`; reserve strip + legend right margin;
  tidy `variable=…` facet text; log cosmetics failures.
- Regression tests: long-name legend truncation + layout, short-name sanity,
  shorten-still-runs when `update_layout` raises.
- Design note: `.issueflows/04-designs-and-guides/summary-legend-long-names.md`.
- `uv run pytest`: 41 passed.
- PR #9 merged to `main` (squash). GitHub issue closed on `/iflow-close`
  (PR body used `Refs #1`, so close was not automatic).
- No `HISTORY.md` at repo root — changelog update skipped.

## Remaining work

None.

PR: https://github.com/cellpy/cellpy-simple-gui/pull/9 (#9, merged)
