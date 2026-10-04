# Group vs individual legend muting (#62)

## Context

cellpy’s Plotly collectors accept `group_legend_muting` (default `True`): a
legend click toggles a whole journal group. With it off, clicks mute one
series. The app did not expose the knob.

## Decision

- Forward `group_legend_muting` from `SummaryPlotSpec` / `CyclesPlotSpec` into
  `collection.plot` via `figures_json` / `figure_json`.
- UI label: **Mute by group** (default on).
- **Disable** (keep visible) when the path forces `group_cells=False`:
  - Summary: **Group avg** on
  - Cycles collector: layout **per_cell**
- Do not expose a separate `group_cells` checkbox; muting alone is enough.
- Cell explorer stays out of scope.

## Colours do not depend on muting (#181)

Turning **Mute by group** off used to recolour the figure: the app colorway was
keyed by Plotly `legendgroup`, which cellpy sets to the group id (muting on) or
the cell name (muting off), so each cell got its own colour and group identity
was lost. Since #181 the colorway is keyed by `collect.cell_groups(records)`:
cells of one group share a hue and differ by lightness, in both muting modes.
See [`plot-appearance.md`](plot-appearance.md).

## Alternatives considered

- Hide the control when N/A — rejected; disable + tooltip keeps layout stable.
- Forward `group_cells` as a second knob — rejected until muting proves insufficient.
