# Issue #81: Keep CE summary panel order consistent (prefer CE on top)

Source: https://github.com/cellpy/cellpy-simple-gui/issues/81

## Original issue text

## Problem / context

On **Cycle summary** with plot type *Capacity + coulombic efficiency*, the vertical facet order of the Coulombic efficiency (CE) panel changes when **Group avg** is toggled:

- **Group avg off:** Charge → Discharge → **CE (bottom)**
- **Group avg on:** Charge → **CE (middle)** → Discharge

That is confusing and not ideal: CE is usually placed on top of capacity panels. Consistency matters more than the exact preferred order, but CE-on-top is the desired default.

This may be a **cellpy** facet-ordering quirk on the averaged (long) vs per-cell (wide) summary plot paths — not confirmed. From the app’s side we would like to control facet order ourselves if upstream does not expose a stable knob.

App today requests columns as `(charge_capacity_*, discharge_capacity_*, coulombic_efficiency)` via `summary_columns_for("capacity_ce", …)`.

## Spec

1. Facet order for `capacity_ce` must be **identical** with Group avg on and off.
2. Preferred order: **CE → Charge → Discharge** (top to bottom).
3. Investigate whether cellpy reorders facets on the group-averaged path; if so, note in `CELLPY_PAINPOINTS.md` and prefer an upstream/order-hook fix when available.
4. If the app must own ordering: apply a single explicit panel order after collect/plot (or when requesting columns) so exports match the on-screen figure.

## Acceptance criteria

- [ ] With *Capacity + coulombic efficiency*, toggling Group avg does not change CE’s vertical position relative to Charge/Discharge.
- [ ] Default order is CE (top), Charge, Discharge (or documented equivalent if cellpy forces a different stable order — but same in both modes).
- [ ] Y-range sidepane labels still match the panels; figure export matches the UI order.
- [ ] If confirmed as a cellpy limitation, a short painpoint note (+ wish for explicit facet order) is recorded.

## Out of scope

- Redesigning other plot types’ panel order (unless the same bug appears and a shared fix is trivial).
- Changing Group avg / spread data semantics.
