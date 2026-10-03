# Status — #175 missing or bad cycles not reported

- [ ] Done

Branch: `cursor/175-missing-cycles-report-2654` (off `main` @ `a4c9dff`).
Plan accepted 2026-10-03 (defaults: inline note + empty-figure text, no figure
annotation, no CSV header, Cycles-tab all-missing guard only).

## What's done

- Captured issue, reproduced the silent drop / blank figure / `KeyError('cycle_num')`
  paths against the running server; plan written and accepted.

## Remaining work

- `core/cycle_report.py` (CycleReport, compress_ranges, build_reports)
- `collect.present_cycle_pairs`, `warnings` on `figure_json` / `_empty_figure_json`
- `plotting.compare_collection` → `(collection, reports)`; reports in compare /
  single-cell explorer figures; Cycles-tab guard; `export.compare_export`
- UI: no range clamp in `parseCycleList`, `cell.notes` strip, placeholder bounds
- Tests (`test_compare.py`, `test_core.py`, `test_api.py`), docs, llms regen
- Manual verification + walkthrough artifacts
