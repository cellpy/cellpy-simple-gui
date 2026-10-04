# Plan — #186 y ranges ignored with Group avg + Spread

## Goal

Per-panel **Y ranges** on the Cycle summary must apply when **Group avg** and
**Spread** are both on, exactly as they do for the plain and group-avg paths.

## Root cause (reproduced with two demo cells in one group)

`collect.figure_json` runs, in order: `collection.plot(spread=True)` →
`_add_spread_hover(fig)` → `_restyle` → `_apply_y_ranges(fig, y_ranges)`.

`_apply_y_ranges` finds the facet axis for a summary column id by reading
`variable=<id>` out of each trace's hovertemplate (`_variable_axis_map`).
cellpy's `spread_plot` does write `variable=charge_capacity_gravimetric` there,
but `_add_spread_hover` (#40) rewrites the mean trace's hovertemplate to
`variable=<pretty axis title>` *before* the ranges are applied — so the column
id no longer appears anywhere, the map misses, cellpy's pretty-title fallback
does not match the app's unit-bearing titles either, and every range is dropped
with a "did not match a summary facet axis" warning.

## Approach

- Resolve the `variable → (xaxis, yaxis)` map right after `collection.plot`,
  before any hover rewrite, and hand it to `_apply_y_ranges` (new optional
  `var_to_axes` argument; it still builds its own map when not given, so the
  other callers are unchanged).
- Keep the human-readable hover from #40 as it is.

## Files to touch

- `src/cellpy_simple_gui/core/collect.py` — `figure_json`, `_apply_y_ranges`.
- `tests/test_core.py` — regression test: group-avg + spread + `y_ranges`
  pins the matching axes (both ends, and one-sided).

## Test strategy

- New core test fails before the change (axes autoranged) and passes after.
- Full `uv run pytest` green; essential CI check green on the PR.
