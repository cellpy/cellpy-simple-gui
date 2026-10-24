# Status — #197 filtering for cycle summary plots

- [x] Done

## What's done

- Cycle summary side pane filters by C-rate through cellpy's step-table
  selection (`rate`, `rate_on`, `rate_std`). Blank rate keeps every cycle.
- The chart and the data export use the same spec. An unmatched rate draws
  "No cycles match C-rate …" and CSV export returns HTTP 400 with that text.
- `uv run pytest` passed.
- Browser check on the demo cells: C-rate 0.05 (charge) kept cycles 1–3 of
  `20180418_sf033_4_cc_01`; clearing the field restored the full summary;
  C-rate 99 showed the empty message. The Cycles tab is unchanged.

## Remaining work

None.
