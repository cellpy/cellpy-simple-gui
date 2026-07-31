# Issue #54 plan: per-panel summary y-range widgets

## Goal

Let users set **min/max y-limits per summary facet panel** (variable) from the
Cycle summary controls, wired through `SummaryPlotSpec` → cellpy’s
`y_ranges={variable: [lo, hi]}` API (cellpy #804, available since 2.1.1.post2).

## Constraints

- cellpy boundary unchanged: only `core/collect.py` / `core/plotting.py` talk to
  cellpy; UI/API stay on Pydantic specs.
- Prefer forwarding `y_ranges` over app-side post-`restyle` axis hacks.
- Omitted / empty panel ranges stay **autorange** (cellpy’s contract).
- Non-empty `y_ranges` **forces independent axes** upstream; the app’s post-plot
  `_apply_share_y` (#47) must not re-link axes when ranges are active, or the
  fixed limits are defeated.
- Scope: **summary plot only** (not cell explorer).
- Update outdated note in
  [`summary-independent-y-scales.md`](../04-designs-and-guides/summary-independent-y-scales.md)
  (still claims #804 is missing).

### Prior art

- `SummaryPlotSpec.share_y` + UI checkbox +
  `tests/test_core.py::test_summary_figure_share_y_*` (#2 / #47).
- `collect._apply_share_y` / `_want_share_y` — re-applies matches after plot
  (spread gap); must coexist with `y_ranges`.
- `collect.summary_columns_for(plot_type, basis)` — exact facet **variable**
  keys cellpy expects in `y_ranges` (smoke-tested: CE range lands on the right
  axis).
- Design doc
  [`summary-independent-y-scales.md`](../04-designs-and-guides/summary-independent-y-scales.md)
  — independent default; per-panel limits deferred to #804 → **implement now**.
- Delegation inventory: “Keep forwarding” `y_ranges` / `share_y`.
- Toolbox: none.

## Approach

1. **Model** — Add optional
   `y_ranges: dict[str, list[float]] | None = None` on `SummaryPlotSpec`
   (variable name → `[lo, hi]`). Validate loosely: only entries with two finite
   numbers and `lo < hi` are forwarded; drop/ignore incomplete pairs.

2. **Core** — In `plotting.summary_figure`, pass `y_ranges=spec.y_ranges or {}`
   into `collect.figures_json`. In `collect.figure_json` /
   `figures_json`, treat “any non-empty forwarded `y_ranges`” as
   `share=False` for `_apply_share_y` (even if the client still sends
   `share_y=True`).

3. **UI** — On the summary controls row (or a compact second row), render
   **min/max number inputs per variable** of the current plot type
   (`summary_columns_for` via existing `plotTypes` + a small client helper, or
   a new `/api/plots/summary-columns?…` if keeping column logic server-only —
   prefer **mirroring column ids in JS from the same source of truth**: expose
   columns on the plot-types payload or a tiny endpoint so the UI does not
   hard-code the table twice).

   - Short labels (e.g. “CE”, “Charge”, “Discharge”) derived from column id.
   - Empty both fields → omit that key (autorange).
   - Changing plot type / basis rebuilds the widget set; keep values that still
     match column ids, drop obsolete keys.
   - When any range is set, **disable or uncheck “Share y-scale”** (tooltip:
     fixed per-panel ranges require independent scales).

4. **Docs** — Refresh `summary-independent-y-scales.md`: independent default +
   optional share + optional per-panel `y_ranges` via cellpy #804.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/models.py` | `y_ranges` on `SummaryPlotSpec` |
| `src/cellpy_simple_gui/core/plotting.py` | Forward `y_ranges` |
| `src/cellpy_simple_gui/core/collect.py` | Suppress `_apply_share_y` when `y_ranges` set; optionally expose columns on plot-types helper |
| `src/cellpy_simple_gui/api/routers/plots.py` | If needed: columns on plot-types response |
| `src/cellpy_simple_gui/web/static/js/app.js` | State, `summarySpec()`, widget helpers |
| `src/cellpy_simple_gui/web/templates/index.html` | Per-panel min/max controls |
| `src/cellpy_simple_gui/web/static/css/app.css` | Compact range-control layout if needed |
| `tests/test_core.py` | Assert CE (or capacity) panel gets `layout.yaxis*.range` when set; share_y + y_ranges → ranges win |
| `.issueflows/04-designs-and-guides/summary-independent-y-scales.md` | Document shipped behaviour |

## Test strategy

```bash
uv run pytest
```

Add focused figure-json tests (same style as `test_summary_figure_share_y_*`):

- `y_ranges={"coulombic_efficiency": [0.9, 1.05]}` → matching axis has that
  `range` and `autorange` false; other panels unset/autorange.
- `share_y=True` + non-empty `y_ranges` → ranges still applied (no shared
  `matches` defeating them).

## Open questions

1. **Persistence** — Session-only (recommended for v1) vs `localStorage` like
   figure theme / color scheme?
2. **Partial input** — Require both min and max before applying a panel
   (recommended), or allow one-sided limits (`null` other end → leave to
   Plotly)?
3. **Share y-scale UX** — Auto-uncheck + disable when any range set
   (recommended), or leave checkbox alone and only fix server-side?
