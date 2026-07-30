# Issue #28 status — Export cells from Manage cells

- [x] Done

## What's done

- Plan accepted (selected cells; cellpy/csv/xlsx; csv zipped; no parquet).
- `cellpy_adapter.export_cell_excel` / `export_cell_csv` + `export.cells_export`.
- `POST /api/export/cells` with optional `CellsExportSpec.cell_ids`.
- Manage cells modal **Export ▾** (`.cellpy` / `.csv` / `.xlsx`).
- Tests: cellpy/xlsx/csv zip + API 400 / happy path.
- `manage-cells-modal.md` updated.

## Remaining work

_(none)_
