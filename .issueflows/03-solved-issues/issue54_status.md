# Issue #54 status

- [x] Done

## What's done

- `SummaryPlotSpec.y_ranges` + validation; forwarded through `plotting` / `collect`.
- `_want_share_y` suppresses share when ranges are set (app re-link cannot defeat limits).
- `/api/plot-types?basis=` returns panel ids/labels; summary UI min/max widgets.
- Share y-scale disabled while any range is set; session-only; both min+max required.
- Tests for CE range application and share_y vs y_ranges precedence.
- Design doc + CELLPY_PAINPOINTS §12 updated for #804 / #54.

## Remaining work

- None.
