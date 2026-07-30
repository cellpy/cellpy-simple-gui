# Issue #39: Group-avg merge puts singleton CE traces on the wrong summary facet

Source: https://github.com/cellpy/cellpy-simple-gui/issues/39

## Original issue text

## Problem / context

With **Group avg** on a multi-cell summary (e.g. capacity + CE), adding another cell from a `.cellpy` file that lands in its **own singleton group** mis-places that cell’s series across facet rows. Hover on a line in the charge-capacity panel can show `variable=coulombic_efficiency`, while capacity-scale values appear in the CE panel.

This is the mixed multi/singleton path from #27: `summary_collections` builds an averaged collection for multi-member groups and a per-cell collection for singletons; `figures_json` then merges with a bare `base.add_trace(tr)` and does **not** remap Plotly facet `xaxis`/`yaxis` (or equivalent) onto the base figure’s row for that variable.

## Spec

- When merging singleton (or second-part) summary figures onto the averaged base, place each trace on the **correct facet row for its `variable`** (same panel as the matching series from the first part).
- Prefer a robust merge (remap subplot ids / use cellpy or Plotly APIs that preserve facets) over “hope add_trace aligns.”
- Keep spread bands only on averaged parts (existing behaviour).
- Reproduce with: ≥1 multi-member group + ≥1 singleton group, plot type `capacity_ce`, Group avg on; assert CE traces are not on the capacity y-axis domain (and vice versa).
- Note any upstream cellpy gap in `CELLPY_PAINPOINTS.md` if the clean fix belongs there.

## Acceptance criteria

- [ ] Mixed group-avg + singleton summary: each series appears only in the facet panel for its variable (capacity vs CE, etc.).
- [ ] Hover/`variable=` for a point matches the panel’s quantity.
- [ ] Pure multi-group (no singletons) and pure singleton (no averaging) plots stay correct.
- [ ] Regression test covers the mixed partition merge (structural: axis/subplot or hover variable vs panel), not pixel asserts.

## Out of scope

- Chart-card theming (#36), spread opacity (#37), axis label wording (#38).
- Changing how groups are assigned in the UI / Manage cells.
- Dropping singletons from group-avg plots (rejected in #27).
