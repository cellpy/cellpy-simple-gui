# Issue #60 plan — summary y_ranges facet miss

## Goal

Per-panel `y_ranges` (e.g. `charge_capacity_gravimetric`) must land on the
matching facet axis of the **final** summary figure JSON without cellpy
“did not match a summary facet row” warnings — especially on multi-part
group-avg + singleton merges.

## Constraints

- App-side fix preferred; no upstream cellpy change unless a one-line forward
  is clearly required.
- Out of scope: cell-explorer axis-range UI.
- Non-empty `y_ranges` still forces independent axes (`_want_share_y` / #54).
- ### Prior art
  - `collect.figures_json` / `_variable_axis_map` / `_remap_trace_axes` —
    multi-part merge (#39).
  - `SummaryPlotSpec.y_ranges` forwarding (#54); design note
    [`summary-independent-y-scales.md`](../04-designs-and-guides/summary-independent-y-scales.md).
  - cellpy `_apply_summary_y_ranges` (annotation + pretty-title match).

## Approach

1. In `figures_json`, **pop** `y_ranges` out of the per-part `collection.plot`
   kwargs so secondary (and spread) parts never try to resolve keys on a
   partial / differently-ordered figure.
2. After merge + `_restyle` + share-y handling, **apply ranges once** on the
   base figure via a small `_apply_y_ranges` helper:
   - Prefer hover `variable=` → axis map (`_variable_axis_map`).
   - Fall back to cellpy’s `_yaxis_key_for_variable` (pretty titles) so spread
     bands (no hover `variable=`) still match.
3. Keep `y_ranges` in the original `plot_kwargs` so `_want_share_y` still
   suppresses re-linking.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/collect.py` | Pop `y_ranges` before per-part plot; `_apply_y_ranges` on merged fig |
| `tests/test_core.py` | Regression: charge (+ CE) ranges on multi-part group-avg path; no warn |
| `.issueflows/04-designs-and-guides/summary-independent-y-scales.md` | Note post-merge apply |

## Test strategy

`uv run --extra dev pytest`

- Extend / add figure-json test: mixed multi+singleton groups, Capacity+CE,
  `y_ranges` for `charge_capacity_gravimetric` (and CE); assert layout axis
  `range` and that the facet-miss warning is not emitted.

## Open questions

None — issue text already specifies the approach; scope stays small (yolo-fit).
