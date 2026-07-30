# Issue #2 plan: Independent y-limits on multi-panel summary plots

## Goal

Keep Capacity + CE (and similar multi-panel summaries) readable when one
variable has outliers: independent auto-scale by default, optional shared
y-scale, with a figure-json regression test — and document that per-panel
fixed limits need cellpy [#804](https://github.com/jepegit/cellpy/issues/804).

## Constraints

- Stay on the app boundary: `SummaryPlotSpec` → `plotting.summary_figure` →
  `collect.figure_json` → `Collection.plot(**kwargs)`. Do not change cellpy
  itself in this issue (companion #804).
- Prefer cellpy’s existing `match_axes` knob (already honored on the collected
  summary path) over client-side Plotly axis hacks.
- No fake per-panel limit UI if cellpy cannot apply ranges per facet row.
- Do not reopen legend long-name work (#1).
- Toolchain: `uv run pytest` only (no new formatter gate).

### Prior art

- `collect.figure_json` / `Collection.plot` —
  [`src/cellpy_simple_gui/core/collect.py`](../../../src/cellpy_simple_gui/core/collect.py):
  already forwards `**plot_kwargs`; **probe confirmed**
  `figure_json(..., match_axes=False)` clears Plotly `yaxis*.matches` on
  capacity_ce facets. **Mirror** — pass through from the plot spec.
- `plotting.summary_figure` —
  [`src/cellpy_simple_gui/core/plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py):
  thin wrapper; currently only forwards `spread`. **Extend** to forward
  `match_axes` from the spec.
- `SummaryPlotSpec` —
  [`src/cellpy_simple_gui/core/models.py`](../../../src/cellpy_simple_gui/core/models.py):
  no axis fields today. **Extend** with a share/match flag (see Approach).
- Summary UI controls —
  [`web/templates/index.html`](../../../src/cellpy_simple_gui/web/templates/index.html) +
  [`web/static/js/app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js):
  plot type / basis / max cycle / group avg / spread. **Coexist** — add one
  checkbox alongside those.
- cellpy `summary_plotter` → `_cycles_plotter(match_axes=True)` —
  `cellpy.plotting.collected` (installed 2.1.1): default shared axes;
  `match_axes=False` → `update_yaxes(matches=None)`. **Use as-is**.
- cellpy `AxisSpec` / `PanelSpec.y_axis.range` —
  `cellpy.plotting.spec`: types exist but **builders do not consume them yet**
  (docstring in upstream). `ce_range` works on the *batch_summary* path, not
  collected summary; `range_y` applies **globally** to all panels — not
  per-variable. **Defer** fixed per-panel limits to #804.
- Design note #1 (`summary-legend-long-names.md`): restyle/legend only —
  **coexist**.
- Toolbox (`00-tools/`): empty. Graphify: absent.

## Approach

1. **Spec field (app):** add `share_y: bool = False` on `SummaryPlotSpec`
   (independent by default). Map to cellpy as
   `match_axes=spec.share_y` in `plotting.summary_figure` →
   `collect.figure_json(..., match_axes=...)`.
   - Name the UI “Share y-scale”; keep the model field `share_y` (clearer than
     exposing `match_axes`).
   - Default `False` for **all** summary plot types (single-panel types are
     unaffected; multi-panel mixed-scale types get the fix without special
     casing). Users who want matched capacity charge/discharge rows can turn
     the checkbox on.

2. **Wire UI:** Alpine `summary.share_y` (default false) → `summarySpec()` →
   POST `/api/plots/summary`. Checkbox in the summary controls row, visible
   whenever the selected plot type produces multiple summary columns (or
   always visible — prefer always, cheap and honest).

3. **Per-panel fixed limits:** **do not ship UI** in this issue.
   - Confirmed gap: collected summary path has no reliable per-facet-row
     y-range API; companion already open:
     https://github.com/jepegit/cellpy/issues/804
   - Record a short design note under
     `.issueflows/04-designs-and-guides/` (decision: independent auto-scale
     now; fixed limits wait on #804) and a pointer in `CELLPY_PAINPOINTS.md`
     if that file’s plotting section is the project’s usual home for this.

4. **Regression tests** (`tests/test_core.py`, figure-json path):
   - `share_y=False` (default): capacity_ce figure has no `layout.yaxis*.matches`
     linking secondary rows to `y`.
   - `share_y=True`: secondary y-axes still report `matches: "y"` (shared).
   - Outlier CE: mutate `coulombic_efficiency` on the summary collection frame
     to ~`1e6`, plot with independent scales, assert capacity-panel series
     data maxima stay on capacity scale (≪ 1e6) **and** axes are unmatched
     (so Plotly autorange cannot crush capacity onto the CE scale).
   - Sanity: normal (unmutated) capacity_ce still returns traces / layout.

5. **Out of scope stays out:** no interactive Plotly axis chrome beyond the
   share toggle; no cellpy PR; no legend work.

## Files to touch

| Path | Change |
| --- | --- |
| [`src/cellpy_simple_gui/core/models.py`](../../../src/cellpy_simple_gui/core/models.py) | Add `share_y: bool = False` to `SummaryPlotSpec`. |
| [`src/cellpy_simple_gui/core/plotting.py`](../../../src/cellpy_simple_gui/core/plotting.py) | Forward `match_axes=spec.share_y` into `figure_json`. |
| [`src/cellpy_simple_gui/web/static/js/app.js`](../../../src/cellpy_simple_gui/web/static/js/app.js) | Default + include `share_y` in `summarySpec()`. |
| [`src/cellpy_simple_gui/web/templates/index.html`](../../../src/cellpy_simple_gui/web/templates/index.html) | “Share y-scale” checkbox wired to `summary.share_y`. |
| [`tests/test_core.py`](../../../tests/test_core.py) | Shared vs independent + CE-outlier regression. |
| `.issueflows/04-designs-and-guides/` | Terse note: independent default + #804 gap. |
| [`CELLPY_PAINPOINTS.md`](../../../CELLPY_PAINPOINTS.md) | Optional short bullet pointing at #804 / per-panel ranges. |

No router signature changes (`SummaryPlotSpec` body already covers new fields).

## Test strategy

- `uv run pytest` (full suite).
- New focused figure-json tests as above; reuse `loaded_library` /
  example-cell fixtures; mutate CE on the collection frame rather than needing
  a special fixture file.
- Manual spot-check optional: Summary tab, Capacity + CE, toggle Share y-scale
  with a cell that has a wild CE point (or after a temporary data tweak).

## Open questions

None blocking — recommended defaults above (`share_y=False` default, UI
checkbox, defer fixed per-panel limits to cellpy #804). Confirm to proceed, or
revise if you want:

- **shared-by-default** instead, or
- **auto** independent only when CE (or mixed units) is in the column set, or
- a **minimal CE min/max** UI that applies a best-effort post-restyle on the CE
  facet row only (app-side hack until #804 lands).
