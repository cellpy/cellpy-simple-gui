# Issue #38: Use cellpy label builders for summary/cycle axis titles

Source: https://github.com/cellpy/cellpy-simple-gui/issues/38

## Original issue text

## Problem / context

Summary (and likely cell-explorer) plots show raw snake_case column names on the y-axes / facet strips, e.g. `charge_capacity_gravimetric` and `coulombic_efficiency`, instead of human labels with units. cellpy already ships label helpers (`cellpy.plotting.quantity_label`, `units_quantity_label`) and the collected Plotly path accepts a `y_label_mapper` for per-variable axis titles. The app does not pass a mapper today; `collect._tidy_facet_annotations` only strips a `variable=` prefix and leaves the raw id.

## Spec

- Build a `y_label_mapper` (or equivalent) for the summary columns we plot, using cellpy’s label builders / units helpers where they cover the column (capacity modes, CE, voltage, IR, C-rate, etc.).
- Pass that mapper through `collection.plot` / `figures_json` so facet row titles and y-axis titles are human-readable (e.g. `Charge capacity (mAh/g)`, `Coulombic efficiency (%)` — exact wording from cellpy when available).
- Prefer cellpy APIs over a hand-rolled rename table; keep a thin local fallback only for columns cellpy cannot label yet, and note gaps in `CELLPY_PAINPOINTS.md` if any.
- Apply the same approach to cell-explorer axis labels where the cycles path exposes the same hooks.
- Do not break legend shortening / restyle from #32.

## Acceptance criteria

- [ ] Summary plot y-axes / facet titles no longer show bare snake_case for the standard plot types (at least capacity_ce, capacity, coulombic_efficiency).
- [ ] Labels include units where cellpy’s builders provide them; gravimetric/areal/absolute basis still make sense.
- [ ] Implementation goes through cellpy label builders / `y_label_mapper` (or documented equivalent), not a parallel hard-coded string table for every column.
- [ ] At least one test asserts a human label (substring / unit) appears in figure layout for a known column.

## Out of scope

- Redesigning plot families or which columns are collected.
- Chart-card theming (#36) or spread-band opacity (#37).
- Full i18n / custom user-authored axis titles.
