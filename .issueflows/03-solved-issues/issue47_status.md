# Issue #47 — Status

Interactive `/iflow-fix` session.

- [x] Done

## Iterative fixes log

- 2026-07-30: Share y-scale ignored with Group avg + Spread — cellpy `spread_plot` never sets facet `matches`; app now re-applies shared y after restyle (`collect._apply_share_y`). Test + CELLPY_PAINPOINTS §12b.
- 2026-07-30: Leaner terminal logging — job start/done/errors, load/ingest/project open-save, export, desktop URL + close (`jobs.py`, routers, `desktop.py`). Still quiet by default (no plot/restyle spam).
- 2026-07-30: Abort stuck imports — job spinner **Cancel** / **Dismiss**; track job id + close SSE; cooperative cancel checks on journal load; cancel API 404 for unknown jobs.

## Remaining work

- None.
