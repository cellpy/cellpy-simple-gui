# Issue #81 — Plan: consistent CE summary panel order

## Goal

Make *Capacity + coulombic efficiency* facet order identical with Group avg on
and off, with **CE → Charge → Discharge** (top → bottom). Prefer an app-owned
order knob so we are not at the mercy of cellpy’s long-frame `variable` order.

## Constraints

- Keep summary collect / y-range / export semantics unchanged; only facet order.
- Y-range sidepane labels must stay aligned with panel order
  (`summary_panels_for` follows `summary_columns_for`).
- Figure export must match the on-screen order (server-side ordering, not a
  client-only Plotly relayout).
- Record a short cellpy painpoint if the upstream quirk is confirmed.

### Prior art

- `summary_columns_for` / `summary_panels_for` — [`collect.py`](../../src/cellpy_simple_gui/core/collect.py): column tuple is the app’s intended panel set; today `capacity_ce` is `(charge, discharge, CE)`.
- `figures_json` / `plotting.summary_figure` — already forward plot kwargs into `collection.plot` (e.g. `y_ranges`, `y_label_mapper`, `share_y`).
- cellpy `sequence_plotter` (summary method) — sets `facet_row="variable"` and passes remaining kwargs into `px.line` / `spread_plot`; **does not** set `category_orders`, so Plotly/pandas unique order wins on long (averaged) frames → alphabetical-ish Charge → CE → Discharge.
- Issue #39 / `#816` — related long/wide facet **axis id** merge; different problem (wrong facet), but same long/wide split.
- Toolbox `00-tools/`: nothing for facet ordering.
- Graph: communities around `figures_json` / `_apply_y_ranges` / summary collect (reuse those paths).

## Approach

1. **Confirm (done in planning):** Group avg off follows column order; Group avg
   on reorders (CE middle). Passing Plotly
   `category_orders={"variable": <columns>}` through `collection.plot` forces
   CE-first in **both** modes. Column-order alone is **not** enough for avg on.
2. Change `summary_columns_for("capacity_ce", …)` to
   `(coulombic_efficiency, charge_capacity_*, discharge_capacity_*)` so UI
   panels / y-range widgets match CE-on-top.
3. In `plotting.summary_figure` (or once in `figures_json` when a column list is
   known), always forward
   `category_orders={"variable": list(columns)}` for summary figures so the
   requested column tuple is authoritative for every plot type — not only
   `capacity_ce`.
4. Add `CELLPY_PAINPOINTS.md` §20 (status table + short note): summary facet
   order on averaged/long frames ignores collect column order unless the app
   passes `category_orders`; wish for cellpy to honour column / category order
   by default.
5. Optional one-liner in
   `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md` if that
   table already lists summary plot kwargs.

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/collect.py` | CE-first `capacity_ce` columns; ensure `summary_panels_for` picks it up |
| `src/cellpy_simple_gui/core/plotting.py` | Forward `category_orders={"variable": list(columns)}` into `figures_json` |
| `CELLPY_PAINPOINTS.md` | §20 + status-table row |
| `tests/test_core.py` | Update `test_summary_panels_for_capacity_ce`; add facet-order test avg on/off → CE top |
| `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md` | Optional inventory note |

## Test strategy

- `uv run pytest tests/test_core.py -q` (or targeted new/updated tests).
- New test: load ≥2 cells, same group; for `group_average` True/False, assert
  top facet axis title is Coulombic efficiency (domain / title order helper).
- Existing y-range / group-avg facet tests should still pass (keys unchanged;
  only row order changes).

## Open questions

None blocking — recommend always forwarding `category_orders` from the columns
tuple (not only for `capacity_ce`). Say if you prefer scoping that to
`capacity_ce` only.
