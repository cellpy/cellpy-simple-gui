# Issue #55 — Plan: cycles collector (per cell / per cycle)

## Goal

Add a multi-cell cycles **collector** with cellpy layouts `per_cell` and
`per_cycle` (Streamlit’s `fig_pr_cell` / `fig_pr_cycle`), sensible widgets and
defaults. **Cell explorer stays one-cell only.**

## Constraints

- cellpy boundary: only `core/collect.py` (+ adapter) import cellpy; plot via
  `Collection.plot(family_kind="cycles", layout=…)`.
- Prefer cellpy knobs over new app science logic (`this-project.md`,
  `cellpy-delegation-inventory.md`).
- **Cell explorer remains single-cell** (picker + metrics + existing curve
  options). Do not overload it into a multi-cell collector.
- **Do not fold the collector into Cycle summary** — that tab is already dense
  (plot type, basis, group avg, spread, share_y, y-ranges) and is summary-series
  data, not voltage–capacity curves.
- Reuse `.chart-row` / `.plot-sidepane` chrome (`plot-sidepane.md`) for the new
  tab.
- Keep theme / color scheme / export for cycles figures.
- Scope: cycles collector UX + API/spec wiring. No ICA/dQdV (#56), no summary
  legend muting (#62), no Streamlit subplot-gap / god-mode knobs.

### Prior art

- `plotting.cycles_figure` — single `CellRecord` + hardcoded
  `layout="per_cell"` ([`core/plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py)).
- `collect.cycles_collection` / `figure_json(..., family_kind="cycles", layout=)`
  — already supports multi-record batches and both layouts
  ([`core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py)).
- `CyclesPlotSpec` — `cell_id`, cycles, mode, method, theme/colors; no `layout`
  ([`core/models.py`](../../../src/cellpy_simple_gui/core/models.py)).
- UI — two tabs today: Cycle summary (selected cells) + Cell explorer (one cell)
  ([`index.html`](../../../src/cellpy_simple_gui/web/templates/index.html),
  [`app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js)).
- cellpy `resolve_collected_layout_kind` —
  `fig_pr_cell`→`per_cell`, `fig_pr_cycle`→`per_cycle`.
- Sibling Streamlit: separate pages for summary collector, cycles collector, and
  cell plotter (`cycles_collector_app.py` defaults `plot_type="fig_pr_cycle"`).
- Toolbox: none relevant.

## Approach

1. **UI — new third tab “Cycles”** (between Cycle summary and Cell explorer, or
   after summary). Selected cells from the sidebar (same as summary). Sidepane:
   **Layout** (Per cell / Per cycle), cycles from/to, max curves, mode, method.
   Chart id e.g. `cyclesChart`. Export menu parallel to summary/cell.
   Defaults: layout **`per_cycle`**; from/to like today’s cell explorer
   (`min` … `min(max, min+9)`); `maxCurves=8`; gravimetric; forth-and-forth.
2. **Cell explorer** — leave as-is for this issue (still one cell,
   `layout="per_cell"` internally). Optional tiny follow-up later: expose layout
   there too; **out of scope** unless trivial while touching shared helpers.
3. **Data model** — Either extend `CyclesPlotSpec` with optional `layout` +
   optional `cell_id` (absent → selected cells), **or** add a small
   `CyclesCollectorSpec` (layout + cycles + mode + method + theme; no
   `cell_id`). Prefer **one spec with optional `cell_id`** to avoid dual export
   paths: `cell_id` set → one cell (Cell explorer); unset → `lib.selected()`
   (Cycles tab).
4. **Core** — `plotting.cycles_figure(records, spec)` (list) + pass
   `layout=spec.layout` (default `per_cycle` for collector; Cell explorer can
   keep sending `per_cell` or omit and we special-case — prefer explicit
   `layout` from each UI). Empty list → empty figure.
5. **API** — `POST /api/plots/cycles` / export: if `cell_id` → that cell; else
   selected. Cycle list from body. Cycle-bound helper for the Cycles tab: union
   of selected cells’ cycle numbers for from/to clamp.
6. **Tests** — Multi-selected demo cells + both layouts; empty selection;
   existing single-`cell_id` tests still pass. API smoke with `layout:
   "per_cycle"` and no `cell_id`.
7. **Design note** — Update `plot-sidepane.md` + brief note in
   `this-project.md` / design parity table if it still says only two plot tabs.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/models.py` | `layout` on `CyclesPlotSpec`; `cell_id` optional |
| `src/cellpy_simple_gui/core/plotting.py` | Multi-record `cycles_figure` + `layout` |
| `src/cellpy_simple_gui/core/export.py` | Same selection / layout wiring |
| `src/cellpy_simple_gui/api/routers/plots.py` | Resolve `cell_id` or selected; optional cycle-bounds helper endpoint if useful |
| `src/cellpy_simple_gui/api/routers/export.py` | Same for cycles export |
| `src/cellpy_simple_gui/web/templates/index.html` | New Cycles tab + sidepane |
| `src/cellpy_simple_gui/web/static/js/app.js` | Cycles state, plot/export, tab switch / relayout |
| `src/cellpy_simple_gui/web/static/css/app.css` | Only if tab/chrome needs a tweak |
| `tests/test_core.py`, `tests/test_api.py` | Collector + layout cases; keep cell_id path |
| `.issueflows/04-designs-and-guides/plot-sidepane.md` | Third tab / Cycles pane |

## Test strategy

```bash
uv run pytest
```

Focus: multi-cell cycles figure both layouts; Cell explorer/`cell_id` path
unchanged; API load → plot cycles without `cell_id`.

## Open questions

1. **Where does the collector live?** — **Resolved (this revision): new “Cycles”
   tab.** Not Cell explorer; not folded into Cycle summary.
2. **Default layout** — Recommend **`per_cycle`** (Streamlit default).
3. **Cycle bounds for multi-cell** — Recommend **union** of cycle numbers for
   from/to clamp; defaults from first selected cell’s min…min+9. Alternative:
   intersection only.
4. **Tab order** — Recommend `Cycle summary | Cycles | Cell explorer`.
5. **Cell explorer layout widget** — Recommend **leave hardcoded `per_cell`**
   this issue (collector is the new tab).
