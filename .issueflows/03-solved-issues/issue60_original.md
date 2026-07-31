# Issue #60: fix: summary y_ranges warn/miss on charge_capacity facet

Source: https://github.com/cellpy/cellpy-simple-gui/issues/60

## Original issue text

### Problem / context
When using per-panel y-ranges (#54) while plotting a project summary, cellpy warns and ignores a range key:

```
UserWarning: y_ranges key 'charge_capacity_gravimetric' did not match a summary facet row; ignoring
```

Seen while opening/plotting project `test_02` (many cells). CE ranges may still work; charge (and possibly discharge) can be skipped.

### Spec
- Reproduce with Capacity + CE and a fixed Charge y-range (min/max set in the side pane), especially with group-avg / mixed group+singleton collections if that triggers it.
- Ensure `y_ranges` keys from `summary_columns_for` (e.g. `charge_capacity_gravimetric`) reliably map onto the matching facet axis on the **final** figure JSON the app returns.
- Likely app fix: in `collect.figures_json`, apply `y_ranges` once on the merged base figure (using hover `variable=` → axis map, same idea as `_variable_axis_map`) instead of forwarding into every `collection.plot` where a secondary part can warn and no-op. Alternatively only pass `y_ranges` into the base part’s plot.
- Add a regression test that sets a charge-capacity range and asserts the corresponding axis `range` is set (cover multi-part / group-avg path if that’s the trigger).

### Acceptance criteria
- [ ] Setting Charge (and Discharge / CE) y-ranges no longer emits the “did not match a summary facet row” warning for valid column ids.
- [ ] Figure JSON has the expected `layout.yaxis*.range` for those panels.
- [ ] `uv run --extra dev pytest` passes, including a new/extended figure-json test.

### Out of scope
- New UI for cell-explorer axis ranges
- Upstream cellpy changes unless a one-line forward is clearly required
