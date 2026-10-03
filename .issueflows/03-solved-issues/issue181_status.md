# Status — #181 keep group colours when "Mute by group" is off

- [x] Done

## What was done

- `collect.cell_groups(records)` maps trace names (batch keys and group names)
  to group ids; `plotting.summary_figure` and `plotting.cycles_figure`
  (`per_cycle` layout) pass it to `figure_json(cell_groups=…)`.
- `collect._apply_colorway` buckets per-cell traces by group and paints each
  group with one hue — the scheme colour at `(group - 1) % len` (so the `safe`
  scheme matches the sidebar swatches) or, for the `cellpy` scheme, the colour
  cellpy already gave the group — fanned into lightness shades per member via
  the new `_shade_series` / `_parse_color` / `_trace_color` / `_paint`
  helpers. Singletons keep the base colour exactly. Traces outside any group
  (group averages, `per_cell` facets coloured by cycle) keep the previous
  order-of-appearance colouring.
- Colouring now runs before legend truncation in `_restyle`, so truncated
  names cannot collide.
- Result is identical with **Mute by group** on or off; muting only decides
  what a legend click toggles.

## Tests

- `tests/test_core.py` (#181 section): `cell_groups` map, `_shade_series`,
  summary colours follow groups for every scheme × both muting modes, both
  muting modes give identical colours, Cycles pane follows groups while
  `per_cell` stays coloured by cycle, group-average traces keep their swatch
  colours. Full suite green.

## Docs

- `.issueflows/04-designs-and-guides/plot-appearance.md` and
  `group-legend-muting.md` updated; README feature line; `llms-full.txt`
  regenerated.

## Remaining

- Nothing. A saturation (rather than lightness) gradient was considered and
  rejected: muted base colours lose their identity when desaturated further.
