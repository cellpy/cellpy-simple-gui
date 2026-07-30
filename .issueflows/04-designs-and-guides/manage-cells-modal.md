# Manage cells modal

**Decision (issue #3):** keep the sidebar Cells list as a compact overview; open a **centered modal** with a dense editable table for bulk library edits. Do not ship a drawer or resizable sidebar for this.

## Behaviour

- Entry: **Manage** on the Cells panel head when cells are loaded.
- Close: Esc, backdrop click, or Close.
- Edits reuse existing APIs (`POST /api/cells/{id}/update`, select-all, delete, clear) via Alpine `updateCell` / `selectAll` / `removeCell` / `clearAll` — no new persistence model.
- Table fields: selected, label, group, mass (API already supports), cycles (read-only), remove.
- Client-only niceties: filter by label, sort by group/name, select-by-group (sequential updates; replot once at end).
- **Export ▾** (issue #28): exports **selected** cells via cellpy `save` / `to_csv` / `to_excel`
  (`POST /api/export/cells?fmt=cellpy|csv|xlsx`). One cellpy/xlsx file is returned bare;
  csv (multi-file) and multi-cell exports are zipped. Reuses `download()` (desktop Save As).

## UI location

- Markup: `web/templates/index.html` (modal after `.layout`)
- Logic: `web/static/js/app.js` (`cellsManagerOpen`, `filteredSortedCells`, …)
- Styles: `web/static/css/app.css` (`.modal-*`, `.cells-table`) using existing theme tokens
