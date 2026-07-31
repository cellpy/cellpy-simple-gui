# Issue #63 status

Interactive `/iflow-fix` session: plot bottom clipping / UI polish.

- [x] Done

## Iterative fixes log

- **2026-07-31** — Plot bottom clipped: stop flex-squashing `.chart-row` into the viewport; pin Plotly div height from `layout.height` before resize; bump `figure_border_height` 90→120 (`app.css`, `app.js`, `collect.py`).
- **2026-07-31** — Sticky plot side pane: `position: sticky` + max-height so Y-ranges / Curves stay visible while scrolling (`app.css`).
- **2026-07-31** — Horizontal chart scroll: `min-width: 0` on main/row, side pane `flex-shrink: 0`, chart-card `overflow-x: auto` + chart `min-width: 560px` so the Y-ranges pane stays on-screen (`app.css`).
