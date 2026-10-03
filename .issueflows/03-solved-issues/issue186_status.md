# Status — #186 y ranges ignored with Group avg + Spread

- [x] Done

Branch: `cursor/186-y-ranges-group-avg-spread-713a` (off `main` @ `8379324`).

## What's done

- Reproduced with two demo cells in one group: with `spread=True` every
  `y_ranges` entry was dropped (`range=None`) while the same spec without
  spread pinned the axes.
- Root cause: `_add_spread_hover` (#40) rewrites the mean traces'
  `variable=<column id>` hover into the pretty axis title *before*
  `_apply_y_ranges` looks the column id up, so no facet axis ever matched.
- Fix (`core/collect.py`): `figure_json` resolves the `variable → axes` map
  straight after `collection.plot` and hands it to `_apply_y_ranges`
  (new keyword `var_to_axes`; other callers unchanged).
- Tests (`tests/test_core.py`): `test_summary_figure_y_ranges_apply_with_group_avg_and_spread`
  (two ranges pinned, third panel still autoranged, spread bands present) and
  `test_summary_figure_y_ranges_one_sided_with_spread`. Both fail before the
  fix and pass after; full `uv run pytest` green.
- `graphify update .` run (tracked graph artifacts refreshed).

## Remaining work

- None.
