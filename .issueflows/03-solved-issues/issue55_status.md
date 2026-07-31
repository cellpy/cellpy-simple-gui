# Issue #55 — Status

- [x] Done

## What's done

- Plan accepted: new Cycles tab; Cell explorer stays one-cell.
- `CyclesPlotSpec.layout` + optional `cell_id` (selected cells when omitted).
- `cycles_figure` / export take a record list; Cell explorer sends `layout=per_cell`.
- API: `GET /api/plots/cycles/bounds`; plot/export resolve `cell_id` or selection.
- UI: Cycles tab (layout, from/to, max curves, mode, method) + export.
- Tests for both layouts + API collector path; design notes updated.
- `uv run pytest` green.

## Remaining work

- Close / PR (chained via `auto_close`).
