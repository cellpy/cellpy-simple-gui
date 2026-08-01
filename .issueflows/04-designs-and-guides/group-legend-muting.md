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

## Alternatives considered

- Hide the control when N/A — rejected; disable + tooltip keeps layout stable.
- Forward `group_cells` as a second knob — rejected until muting proves insufficient.
