# Plan — Issue #177: GUI color scheme and layout

Source: https://github.com/cellpy/cellpy-simple-gui/issues/177

## Goal

Refresh the app chrome (colors, type, spacing, control density) so the window
looks current, while keeping the same screens: left journal, plot tabs, chart.

## Constraints

- Frontend only. No API, job, or cellpy changes.
- Keep the DOM regions tests already read: `.sidebar`, the Data hint, `.main`,
  `.tabs`. `tests/test_api.py` checks sidebar hint text, not pixels.
- Light and dark both move. Dark stays the default. Theme toggle and
  `localStorage` key `csg-theme` stay.
- Plot **figure theme** and **Colors** (cellpy / safe / muted / …) stay as they
  are. Categorical vs gradient is [#176](https://github.com/cellpy/cellpy-simple-gui/issues/176).
- Same information architecture unless the chosen option below says otherwise.
- README screenshots (`docs/img/`) go stale. Update them in this issue only if
  you ask; otherwise a follow-up.

### Prior art

- Theme tokens and the two-column grid live in
  [`src/cellpy_simple_gui/web/static/css/app.css`](../../../src/cellpy_simple_gui/web/static/css/app.css)
  (`:root[data-theme]`, `.layout` = `330px 1fr`, `.topbar`, `.tabs`).
- Shell markup is
  [`src/cellpy_simple_gui/web/templates/index.html`](../../../src/cellpy_simple_gui/web/templates/index.html)
  (top bar, sidebar Project / Data / cells, main tabs).
- Toggle is `toggleTheme()` in
  [`src/cellpy_simple_gui/web/static/js/app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js).
  Coexist: do not replace that mechanism.
- Closed #32 / #36 / #37 already own figure theme and plot color schemes.
  Mirror their boundary: app chrome here, plot chrome there.
- Toolbox: none. Graph: community "layout" is plotly figure layout, not this UI.

## Approach

Three layouts. **Recommended: A.** B and C rebuild the shell.

### A — Quiet lab (recommended)

Keep top bar + 330px sidebar + plot tabs. Change the paint and the density.

- Drop the body radial gradient and the blue→teal gradient on primary buttons.
  One accent (teal `#1f8f6b`, same family as the README badge). Neutral panels.
- Solid top bar (the transparent bar was so the gradient showed through).
- Slightly smaller radius, calmer borders, no uppercase panel titles.
- Chart controls wrap in one compact row; the chart keeps the rest of the column.
- Sidebar width stays 330px so Project / Data fields do not reflow.

### B — Plot-first

Sidebar collapses to an icon rail. Project, Data, and the cell list open in a
drawer. Tabs move into the top bar. The chart fills the window. Daily cell
selection takes an extra click.

### C — Top strip

No left sidebar. Project actions and the cell list become a horizontal strip
under the top bar. Tabs and the chart sit below. Wide plots; a long cell list
scrolls sideways.

Implement only the option you accept. A is CSS plus small class tweaks in the
template. B or C also move blocks in `index.html` and the layout rules in
`app.js` only if a click target moves.

## Files to touch

- `src/cellpy_simple_gui/web/static/css/app.css` — tokens, top bar, panels, buttons, tabs, control row.
- `src/cellpy_simple_gui/web/templates/index.html` — class hooks for the compact control row (A), or moved blocks (B/C).
- `src/cellpy_simple_gui/web/static/js/app.js` — only if B adds a drawer open/close flag.

## Test strategy

`uv run pytest` from the worktree. No new pixel test. Existing API HTML checks
must still pass. After the change, open `./run` and check dark and light on
Cycle summary, Cycles, and Cell explorer, plus one modal (Add cells).

## Open questions

1. **Which layout?** A (recommended), B, or C.
2. **README screenshots** in this issue, or later?
