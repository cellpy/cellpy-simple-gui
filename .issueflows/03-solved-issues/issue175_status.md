# Status — #175 missing or bad cycles not reported

- [x] Done

Branch: `cursor/175-missing-cycles-report-2654` (off `main` @ `a4c9dff`).
PR: https://github.com/cellpy/cellpy-simple-gui/pull/178
Plan accepted 2026-10-03 (defaults: inline note + empty-figure text, no figure
annotation, no CSV header, Cycles-tab all-missing guard only).

## What's done

- Reproduced the three failure modes against the running server: silent drop
  (compare, one cell lacks the cycle), blank figure (compare, no cycle exists),
  `Could not render this plot ('cycle_num')` (single-cell explorer).
- `core/cycle_report.py` (new, pure): `CycleReport`, `compress_ranges`,
  `build_reports`, `messages` — "cycles 22–24, 50 not in data (has 1–21)" /
  "cycle 7 could not be read".
- `collect.present_cycle_pairs` (mirror of `restrict_to_cycle_pairs`);
  `figure_json` / `_empty_figure_json` take `warnings` → `layout.meta.warnings`.
- `plotting.compare_collection` → `(collection, reports)`; pre-check against
  `cycle_numbers` (never collects when nothing exists), post-check for
  unreadable cycles. Reports in `compare_figure`, single-cell `cycles_figure`,
  `ica_figure`, `dva_figure`; Cycles-tab all-missing guard
  (`None of the N selected cells has cycles …`); `export.compare_export` 400
  says why.
- UI: `parseCycleList` no longer clamps to the cell range; pick range shown as
  the input placeholder; `cell.notes` + persistent `.plot-note` strip above
  `#cellChart`, fed from `layout.meta.warnings`.
- Tests: 20 new (`tests/test_compare.py` core + essential API,
  `tests/test_core.py` cycle-report units + single-cell explorer). Full suite
  green (`uv run pytest`).
- Docs: `docs/guides/03-plotting.md` "Say when a cycle is not there" (runnable
  block), `compare-cells.md` addendum, `CELLPY_PAINPOINTS.md` §37, llms regen.
- Manual browser walkthrough recorded
  (`/opt/cursor/artifacts/compare_missing_cycles_reported_walkthrough.mp4`).

## Remaining work

- None. Not done by design (see plan open questions): figure annotation for
  static exports; `X-CSG-Warnings` header for partial compare CSV.
