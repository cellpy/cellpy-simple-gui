# Plan — Issue #39

## Goal

When merging singleton summary traces onto a group-averaged faceted base, place each trace on the facet row for its `variable`.

## Approach

1. From the base figure layout, build `variable → (xaxis, yaxis)` using y-axis titles.
2. Before `add_trace` from later parts, read `variable=` from the trace hovertemplate and remap `xaxis`/`yaxis`.
3. Leave spread-only-on-averaged behaviour unchanged.
4. Note upstream facet-id mismatch (long averaged vs wide per-cell subplot order) in `CELLPY_PAINPOINTS.md`.
5. Regression test: mixed multi+singleton `capacity_ce` with group avg — hover variable matches y-axis title for singleton traces.

## Files to touch

- `src/cellpy_simple_gui/core/collect.py`
- `tests/test_core.py`
- `CELLPY_PAINPOINTS.md`
- `.issueflows/04-designs-and-guides/group-average-and-figure-export.md`

## Test strategy

- Structural test on mixed partition merge (axis title vs hover variable).
- Existing group-avg tests must stay green.
