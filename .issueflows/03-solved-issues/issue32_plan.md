# Issue #32 — Plan: plot appearance (theme + color scheme)

## Goal

Let users pick a **figure theme** (light / dark / match app shell) and a small
**color scheme** for summary + cell-explorer plots (and static figure export),
preferring cellpy plotting hooks where they help and keeping `_restyle` thin for
legend/facet polish we already own. Also bump cellpy to **≥2.1.1.post2** per the
issue comment.

## Constraints

- cellpy boundary: only `core/cellpy_adapter.py` and `core/collect.py` import
  cellpy (`this-project.md`). Theme/color application that needs cellpy lives in
  `collect`; UI/routers stay cellpy-free.
- Export must reuse the same figure builders (`group-average-and-figure-export.md`)
  so PNG/SVG/PDF match the on-screen look.
- Out of scope: per-cell color pickers, matplotlib export, redesigning the app
  chrome theme system.
- No new toolbox scripts expected; keep changes in existing plot/UI paths.
- Document any new cellpy friction in `CELLPY_PAINPOINTS.md` (§11 already covers
  restyle wish).

### Prior art

- `collect._restyle` / `_shorten_legend` / `figure_json` / `figures_json` —
  [`src/cellpy_simple_gui/core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py)
  — hard-coded white card + Inter fonts; **mirror / extend** with theme tokens,
  keep legend/facet logic.
- `library.PALETTE` / `CellRecord.color()` —
  [`src/cellpy_simple_gui/core/library.py`](../../../src/cellpy_simple_gui/core/library.py)
  — UI swatches only today; plot series colors come from cellpy/Plotly defaults.
  **Coexist** for v1 (swatches stay; plot colorway is independent unless we
  decide otherwise — see Open questions).
- `SummaryPlotSpec` / `CyclesPlotSpec` —
  [`src/cellpy_simple_gui/core/models.py`](../../../src/cellpy_simple_gui/core/models.py)
  — extend with appearance fields so plot + export share one path.
- `plotting.summary_figure` / `cycles_figure` —
  [`src/cellpy_simple_gui/core/plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py)
  — thin pass-through; forward new kwargs into `collect.figure*_json`.
- Shell theme via `localStorage` `csg-theme` + `toggleTheme` /
  `relayoutCharts` — [`app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js);
  **mirror** for figure prefs (`csg-figure-theme`, `csg-color-scheme`).
- cellpy `plotting.theme.make_plotly_template` /
  `make_collector_templates` — axis/collector templates, **not** a light/dark
  shell hook. Use if a collector template registers cleanly; otherwise keep
  app-side theme tokens and note the gap in painpoints.
- Graph: Community around `figure_json` / `_restyle` / `SummaryPlotSpec`
  (collect + plotting hubs); god-node adjacency confirms these are the touch
  points. Toolbox: none.

## Approach

1. **Dependency** — Raise `cellpy` to `>=2.1.1.post2` in `pyproject.toml` and
   `uv lock` / sync. Quick smoke that existing summary/share_y tests still pass.

2. **Appearance model** — Add to both plot specs (shared defaults):
   - `figure_theme: Literal["light", "dark"]` — **resolved** value the server
     always receives (UI resolves `"match"` client-side from `this.theme`
     before POST). Keeps the API dumb and export deterministic.
   - `color_scheme: Literal["cellpy", "safe", "muted"]` (names TBD; curated
     set of 3: cellpy/default + app `PALETTE`/"safe" + one readable alt).
   - Defaults: `figure_theme="light"`, `color_scheme="cellpy"` (export-friendly
     until the user opts in).

3. **Server restyle** — Refactor `_restyle(fig, *, figure_theme, color_scheme)`:
   - Theme token tables for paper/plot bg, font, grid, axis, legend bg
     (light ≈ current look; dark ≈ readable on dark shell).
   - After cellpy `collection.plot(...)`, apply **colorway** to traces (cycle
     discrete colors; leave fill/spread bands coherent). Prefer passing through
     any `color_discrete_sequence` / template kwargs cellpy forwards via
     `**opts`; if ignored, set `marker/line.color` post-hoc in `_restyle`.
   - Try registering/using a cellpy collector template when it improves axes;
     do **not** grow a second restyle path if the template fights legend polish.
   - Thread theme/scheme through `figure_json` / `figures_json` /
     `_empty_figure_json` and `plotting.*_figure`.

4. **UI** — On summary + cell explorer control bars: two `<select>`s (Figure
   theme: Light / Dark / Match app; Color scheme: …). Persist with
   `localStorage`. On change → re-plot current tab. When figure theme is
   **Match app**, `toggleTheme` must re-plot (not only `Plotly.Plots.resize`).
   Include resolved `figure_theme` + `color_scheme` in `summarySpec()` /
   `cellSpec()` so figure export stays in sync.

5. **Painpoints** — Update §11: note what we still post-process vs what
   cellpy templates cover after the bump; keep the wish for a first-class
   `FigureSpec`/theme hook if still missing.

6. **Design note** — Short entry under
   `.issueflows/04-designs-and-guides/` (appearance / theme tokens + API
   “resolved theme” choice) so the next plot issue does not re-litigate it.

## Files to touch

| Path | Change |
|------|--------|
| `pyproject.toml` / `uv.lock` | cellpy `>=2.1.1.post2` |
| `src/cellpy_simple_gui/core/models.py` | `figure_theme`, `color_scheme` on plot specs |
| `src/cellpy_simple_gui/core/collect.py` | theme tokens, colorway, `_restyle` / `figure*_json` signatures |
| `src/cellpy_simple_gui/core/plotting.py` | forward appearance from specs |
| `src/cellpy_simple_gui/web/static/js/app.js` | state, localStorage, specs, match→replot |
| `src/cellpy_simple_gui/web/templates/index.html` | controls on both plot tabs |
| `src/cellpy_simple_gui/web/static/css/app.css` | only if control layout needs a tweak |
| `tests/test_core.py` | theme bg assert + one color_scheme path (no pixel asserts) |
| `CELLPY_PAINPOINTS.md` | §11 refresh |
| `.issueflows/04-designs-and-guides/plot-appearance.md` | short design decision |
| `.issueflows/01-current-issues/issue32_status.md` | created at build time |

No router changes expected if specs already flow through existing POST bodies.

## Test strategy

- Command: `uv run pytest` (from repo root; see `this-project.md`).
- Add/extend core tests:
  - `figure_theme="dark"` → layout `paper_bgcolor` / font color match dark tokens.
  - `color_scheme="safe"` (or chosen id) → at least one trace color from that
    colorway (structural, not pixel).
  - Existing summary / share_y / legend / export tests still green after the
    cellpy bump and default light theme.

## Open questions

1. **Default figure theme** — Recommend **`light`** (export-friendly; current
   look). Alternative: default **`match`** so dark-shell users get dark figures
   immediately. Prefer light unless you want match.
2. **Cell-list swatches vs plot colorway** — Recommend **leave swatches on
   `PALETTE`** for v1 (out of scope to recolor the library UI). Or sync swatches
   to the selected scheme (slightly more work, nicer consistency).
3. **Color scheme names / third palette** — Propose `cellpy` (upstream/default),
   `safe` (current `library.PALETTE`), `muted` (lower-saturation qualitative).
   OK, or swap the third for something else?
4. **cellpy bump in this PR** — Recommend **yes** (issue comment). Any reason to
   split?
