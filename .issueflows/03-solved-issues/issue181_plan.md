# Plan — #181 keep group colours when "Mute by group" is off

## Findings

- cellpy colours per-cell traces by **group** whenever `group_cells` is on,
  independent of `group_legend_muting`; muting only decides what goes on
  `legendgroup` (the group number, or the cell name).
- The app's own colorway pass (`collect._apply_colorway`, used by the `safe`
  and `muted` schemes) keys colours by `legendgroup or name`. With muting off
  that key is the cell name, so every cell gets its own colour — the issue.
- With muting on, cells of one group are drawn in **identical** colours (cellpy
  removes the sub-group markers), so the members cannot be told apart either.
- `library.PALETTE` (= the `safe` scheme) also paints the sidebar swatches by
  `(group - 1) % len`; the plot used order of appearance instead.

## Approach

Colour by group, shade by member — in both muting modes, for every scheme:

1. `collect.cell_groups(records)` → `{batch key or group name: group}`;
   `plotting` passes it to `figure_json(cell_groups=…)` for the summary
   (ungrouped) and the Cycles pane (`per_cycle` layout; `per_cell`/`film`
   colour by cycle and are left alone).
2. `_apply_colorway(fig, scheme, cell_groups=…)`: traces are bucketed by group
   via name / legendgroup lookup. A group's base colour is the scheme colour at
   `(group - 1) % len` (so `safe` matches the sidebar swatches, and colours
   stay put when a group disappears) or, for the `cellpy` scheme, the colour
   cellpy already gave the group. Members of a multi-cell group get a lightness
   gradient around the base (`_shade_series`, HLS, clamped so nothing goes
   white/black); singletons keep the base exactly. Ungrouped traces keep the
   previous order-of-appearance behaviour. Colouring moves ahead of legend
   truncation in `_restyle` so truncated names cannot collide.
3. Tests: muting off keeps one hue per group (safe scheme); members of a group
   get distinct shades of the same hue in both muting modes; `cellpy` scheme
   shades from cellpy's own group colour; `per_cell` layout untouched; `safe`
   base colour equals the sidebar swatch.
4. Design doc (`group-legend-muting.md` / `plot-appearance.md`) + README line.
