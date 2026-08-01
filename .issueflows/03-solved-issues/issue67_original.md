# Issue #67: Cell explorer dQ/dV: Charge/Discharge direction has no effect (and joins half-cycles)

Source: https://github.com/cellpy/cellpy-simple-gui/issues/67

## Original issue text

## Problem / context

In Cell explorer → Plot **dQ/dV**, switching **Direction** between Charge and Discharge does not change the figure. The plot always shows both positive and negative dQ/dV lobes for each cycle. At the high-V end the two lobes should meet near y=0; instead Plotly can draw a spurious connection (e.g. a horizontal join at low V), because charge and discharge points are in the same trace.

Reproduced after #56. App forwards `direction` into `Collection.plot(family_kind="ica", direction=…)`.

## Spec

1. **Confirm / document cause:** cellpy `ica_plotter` → `_cycles_plotter` → `sequence_plotter` only calls `_select_direction` for `method=="film"`, not for default `fig_pr_cell`. So `direction` is a no-op for normal ICA line plots. Charge vs Discharge UI cannot work until data is filtered.
2. **App fix:** before plotting (and for figure export), filter the ICA collection (or frame) to `spec.direction` so Charge and Discharge actually differ. Prefer filtering in our `ica_figure` / collect path so we do not depend on cellpy’s film-only filter.
3. **CELLPY_PAINPOINTS:** extend §16 (or add a sibling note): `direction` is documented on `ica_plotter` but ignored for `fig_pr_cell` line plots; only `film` filters. Wish: call `_select_direction` for ICA line layouts (and support `both` as separate series / no join).
4. Optional: file upstream cellpy issue once the app workaround is in.

## Acceptance criteria

- [ ] With the same cell/cycles/resolution, Charge and Discharge produce clearly different figures (e.g. predominantly +dQ/dV vs −dQ/dV for typical Si/graphite half-cells).
- [ ] No spurious line joining charge and discharge segments within one cycle when a single direction is selected.
- [ ] Export figure follows the same filtered direction as the on-screen plot.
- [ ] Pain point note updated; pytest covers charge ≠ discharge for a demo cell.

## Out of scope

- True `both` overlay with a proper break between half-cycles (upstream wish).
- dV/dQ (dva).
- Multi-cell ICA collector.
