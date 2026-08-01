# Plan — Issue #62: Group vs individual Plotly legend muting

## Goal

Expose cellpy’s `group_legend_muting` as a checkbox on **Cycle summary** and **Cycles** (collector), so users can choose mute-by-group vs mute-per-cell legend clicks. Default stays cellpy’s `True`.

## Constraints

- Cellpy boundary: only forward through `core/models` → `core/plotting` → `collect.figures_json` / `figure_json` → `collection.plot`; no UI/router imports of cellpy.
- Cell explorer curve legend grouping stays out of scope (issue body).
- Do not invent a second `group_cells` UI unless muting alone is insufficient — prefer the smallest knob.
- When **Group avg** is on, cellpy forces `group_cells=False` and skips `legend_replacer` — mute-by-group is meaningless; hide or disable the control.
- Cycles **per_cell** layout forces `group_cells=False` upstream — same hide/disable rule.
- Existing `_shorten_legend` / `_restyle` stay as-is; only ensure forwarding still works after restyle.

### Prior art

- `SummaryPlotSpec.group_average` / `spread` + checkbox pattern in [`index.html`](../../src/cellpy_simple_gui/web/templates/index.html) / [`app.js`](../../src/cellpy_simple_gui/web/static/js/app.js) `summarySpec()` — mirror for the new flag.
- [`plotting.summary_figure`](../../src/cellpy_simple_gui/core/plotting.py) → [`collect.figures_json`](../../src/cellpy_simple_gui/core/collect.py) already forwards `share_y` / `y_ranges` / chrome as `**plot_kwargs` into `collection.plot` — add `group_legend_muting` the same way.
- [`plotting.cycles_figure`](../../src/cellpy_simple_gui/core/plotting.py) → `figure_json` same pattern for Cycles.
- cellpy `sequence_plotter` / `summary_plotter`: `group_legend_muting` (default `True`); `legend_replacer` only when `group_cells` is True; `group_it` forces `group_cells=False`; `fig_pr_cell` forces `group_cells=False`.
- Design docs: [`group-average-and-figure-export.md`](../04-designs-and-guides/group-average-and-figure-export.md), [`plot-sidepane.md`](../04-designs-and-guides/plot-sidepane.md), [`summary-legend-long-names.md`](../04-designs-and-guides/summary-legend-long-names.md) (legend chrome — coexist, no change).
- Toolbox: none relevant.

## Approach

1. **Models** — Add `group_legend_muting: bool = True` to `SummaryPlotSpec` and `CyclesPlotSpec`.
2. **Plotting** — Pass `group_legend_muting=spec.group_legend_muting` into `figures_json` / `figure_json` (summary + cycles). Figure export already goes through those helpers — no separate export wiring.
3. **UI — Summary** — Checkbox next to Group avg / Spread, label **Mute by group** (title: legend click toggles whole journal group vs one cell). Bound to `summary.group_legend_muting`; included in `summarySpec()`. Disable (or hide) when `summary.group_average` is true.
4. **UI — Cycles** — Same checkbox on the Cycles collector controls or sidepane (`cycles.group_legend_muting` → `cyclesSpec()`). Disable when `cycles.layout === 'per_cell'` (cellpy forces `group_cells=False`). Leave Cell explorer untouched.
5. **Do not forward `group_cells`** unless a smoke check shows muting-off still leaves group-linked legends (unlikely: `legend_replacer(..., group_legends=False)` is the intended individual path). Revisit only if needed.
6. **Manual smoke** — multi-cell same group: summary with Mute by group on → legend click mutes group; off → single series. Cycles with layout **per cycle** same check. Confirm Group avg / per_cell disable paths don’t error.
7. **Design note** — Short entry under `.issueflows/04-designs-and-guides/` recording the knob + disable rules (optional if build is tiny; preferred for the group-avg interaction).

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/models.py` | `group_legend_muting` on summary + cycles specs |
| `src/cellpy_simple_gui/core/plotting.py` | Forward into `figures_json` / `figure_json` |
| `src/cellpy_simple_gui/web/static/js/app.js` | State + `summarySpec` / `cyclesSpec` |
| `src/cellpy_simple_gui/web/templates/index.html` | Checkboxes + disable/show rules |
| `tests/test_core.py` | Light assert kwarg forwarded (and/or legendgroup equality when True) |
| `.issueflows/04-designs-and-guides/` | Brief decision note (if non-trivial) |

## Test strategy

- `uv run --extra dev pytest`
- Unit: call `summary_figure` / `cycles_figure` with `group_legend_muting=False` and True; assert forwarded into `collection.plot` (monkeypatch) **or** assert Plotly `legendgroup` sharing among same-group cells when True and distinct when False (if stable with demo data).
- No new e2e required; manual Plotly legend click smoke as above.

## Open questions

1. **Label copy** — recommend **Mute by group** (matches cellpy wording). Prefer different UI text?
2. **Disable vs hide** when N/A (Group avg / per_cell) — recommend **disable + title tooltip** (keeps layout stable). Hide instead?
3. **Cycles placement** — recommend checkbox in Cycles **sidepane** under Collector (layout-adjacent). Prefer top controls row instead?
