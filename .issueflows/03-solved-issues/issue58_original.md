# Issue #58: Add a plot side pane and match the top bar to the app background

Source: https://github.com/cellpy/cellpy-simple-gui/issues/58

## Original issue text

### Problem / context
After #54, per-panel y-range widgets sit in the Cycle summary top controls row and crowd it. The chart card also leaves unused space to the right of the figure. Cell explorer has the same full-width chart layout and a dense top bar (cycles / max curves / mode / method). Separately, the sticky top bar (brand / project badge) reads as a different strip than the app background.

### Spec
- **Top bar:** make `.topbar` use the same background as the app shell (match `body` / `--bg`, drop the distinct translucent panel wash) so it blends with the page background in both light and dark themes. Keep border/contrast only if still needed for separation.
- Shared layout: wrap each tab’s chart in a `.chart-row` with the figure + a right `.plot-sidepane` using the same shell chrome (`--panel` / `--line`), not plot-paper colors.
- **Cycle summary:** move Charge / Discharge / CE (etc.) y-range min/max widgets into the side pane; keep plot type, basis, max cycle, group avg / spread / share y, theme, colors, export in the top bar.
- **Cell explorer:** same side-pane chrome; move cycles from/to, max curves, mode, and method into the pane; keep cell select, theme, colors, export (and metrics strip) as they are.
- On layout change / tab show, resize Plotly (`summaryChart` / `cellChart`) so the figure fills the narrower card.
- No new axis-range API on cell explorer in this issue.

### Acceptance criteria
- [ ] Top bar background matches the app background in light and dark themes.
- [ ] Summary top bar no longer contains y-range widgets; they live in the right pane and still apply ranges as in #54.
- [ ] Cell explorer top bar is thinner; cycle/mode/method controls live in a matching right pane.
- [ ] Both panes match app shell styling; charts reflow correctly after resize / theme change.
- [ ] Existing summary/cell plot behaviour and tests still pass.

### Out of scope
- Cell-explorer x/y range widgets
- Collapsible / hideable pane
- Moving theme/colors into the side pane
