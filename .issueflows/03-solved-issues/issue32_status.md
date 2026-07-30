# Issue #32 — Status

- [x] Done

## What's done

- Plan confirmed (defaults: light theme, swatches stay on PALETTE, schemes cellpy/safe/muted, cellpy bump in this PR).
- Bumped `cellpy` to `>=2.1.1.post2` (`pyproject.toml` / `uv.lock`).
- Appearance fields on `SummaryPlotSpec` / `CyclesPlotSpec`; themed `_restyle` + `_apply_colorway` in `collect.py`; forwarded via `plotting.py`.
- UI: Figure theme (Light / Dark / Match app) + Colors (cellpy / safe / muted) on both plot tabs; `localStorage`; match → replot on shell theme toggle; specs include appearance for export.
- Tests: dark theme tokens + safe colorway; full `uv run pytest` green.
- `CELLPY_PAINPOINTS.md` §11 refresh; design note `plot-appearance.md`; project brief cellpy floor updated.

## Remaining work

- None.
