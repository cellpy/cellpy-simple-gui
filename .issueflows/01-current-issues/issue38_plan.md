# Plan — Issue #38: cellpy label builders for axis titles

## Goal

Summary (and cycles where hooks exist) y-axis / facet titles use cellpy label
builders with units — e.g. `Charge capacity (mAh/g)` / areal `mAh/cm²` — via
`y_label_mapper`, not bare snake_case or unit-less title-case.

## Constraints

- Prefer `cellpy.plotting.quantity_label` / `units_quantity_label` + pass
  `y_label_mapper` into `collection.plot` / `figures_json`.
- Thin local fallback only where cellpy cannot label (note in painpoints).
- Do not break legend shortening / restyle (#32) or y-range keying (#54/#60).
- Out of scope: plot-family redesign; cycles facet strip `cell=` / `cycle_num=`
  prettying (CELLPY_PAINPOINTS §15 / #820) unless free.

### Prior art

- **Current state (post #52 / cellpy #801):** summary y-titles are already
  humanized (`Charge Capacity`, `Coulombic Efficiency`) via cellpy’s default
  `_pretty_variable_label`, but **without units** and **basis-blind** (areal
  still says “Charge Capacity”). Snake_case acceptance is largely met; units
  acceptance is not.
- **Verified:** `figures_json(..., y_label_mapper={…})` reaches cellpy and
  updates y-axis titles (cleaner may insert `<br>` before units).
- [`units_quantity_label("Charge capacity", "capacity", mode=…)`](../../.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md)
  → correct mode units; tidy `cm**2` → `cm²` to match `CAPACITY_UNITS` / #72.
- [`quantity_label("Coulombic efficiency", "%")`](../../src/cellpy_simple_gui/core/collect.py)
  for CE (no physical_property for efficiency).
- Cycles path (#72): already forwards `x_unit`; y is `Voltage (V)`. No summary
  `y_label_mapper` equivalent needed there.
- [`test_summary_figure_pretty_axis_labels`](../../tests/test_core.py) — strengthen
  to require unit substrings / basis difference.
- `_PANEL_LABELS` — short UI widget labels; leave alone (not axis titles).
- Toolbox: none.

## Approach

1. **Helper** `summary_y_label_mapper(columns) -> dict[str, str]` in `collect.py`:
   - Parse mode suffix (`_gravimetric` / `_areal` / else absolute for capacity*).
   - Capacity / capacity_loss → `units_quantity_label(< Capitals name >, "capacity", mode=)`.
   - CE / cumulated CE → `quantity_label(..., "%")`.
   - End voltages → `units_quantity_label(..., "voltage")`.
   - IR → `units_quantity_label(..., "resistance")`.
   - C-rate → `quantity_label(..., "C")` (do **not** use `physical_property="current"` → Amperes).
   - Unknown → cellpy `_pretty_variable_label(col)` fallback (import from
     `cellpy.plotting.collected` if stable, else title-case strip).
   - Normalize `**2` → `²` in the final string.
2. **Wire** mapper into `plotting.summary_figure` → `figures_json` (and any
   single-collection summary path). Only set when not already provided by caller.
3. **Cycles / cell explorer:** confirm axes already unit-aware (#72); no change
   unless a gap shows up. Keep `_tidy_facet_annotations` as narrow fallback.
4. **Tests:** extend pretty-label test — `capacity_ce` gravimetric titles contain
   `mAh/g` (and CE `%`); areal contains `mAh/cm` and not `mAh/g` on capacity axes.
5. **Docs — yes, add a painpoint** (status table + new §18). Gaps that force the
   app mapper today:

   | Gap | Why it hurts |
   | --- | --- |
   | Default `_pretty_variable_label` / `_default_summary_y_label_mapper` only append units when a Batch-style `units=` dict is passed | `Collection.plot` path does not pass it → unit-less “Charge Capacity” even though #801 pretty-prints names |
   | No `CellpyUnits` physical property for coulombic efficiency | `units_quantity_label` cannot build CE; apps use `quantity_label(..., "%")` |
   | No C-rate property (`current` → Amperes is wrong) | Apps must hard-code `quantity_label(..., "C")` |

   Draft §18 title: **Summary default y-labels omit units (and CE / C-rate have
   no unit-spec hooks)**. Wish: default mapper (or `units_quantity_label` coverage)
   should produce unit-bearing labels from column id + mode without a Batch
   `units=` bag; add efficiency / C-rate to the unit spec (or document the
   canonical label helpers). Keep §15 (cycles facet strips) and §17 (`x_unit`)
   as separate items — do not fold them into §18.

   Also add an inventory row: app keeps forwarding `y_label_mapper` until that
   lands.

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/collect.py` | `summary_y_label_mapper` helper |
| `src/cellpy_simple_gui/core/plotting.py` | Pass mapper from `summary_figure` |
| `tests/test_core.py` | Unit/basis assertions on axis titles |
| `.issueflows/04-designs-and-guides/cellpy-delegation-inventory.md` | Record mapper ownership |
| `CELLPY_PAINPOINTS.md` | Status-table row + new §18 (units on default summary labels; CE / C-rate) |
| `.issueflows/01-current-issues/issue38_status.md` | Track during build |

## Test strategy

- `uv run pytest` (focus summary figure label tests + y_ranges regressions).
- Manual: Cycle summary → capacity_ce gravimetric vs areal; titles show units.

## Open questions

None blocking. Recommended: normalize `cm**2` → `cm²` in app after cellpy
returns the label (same polish as #72 `CAPACITY_UNITS`).
