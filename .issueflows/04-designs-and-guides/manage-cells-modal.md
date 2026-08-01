# Manage cells modal

**Decision (issue #3):** keep the sidebar Cells list as a compact overview; open a **centered modal** with a dense editable table for bulk library edits. Do not ship a drawer or resizable sidebar for this.

## Behaviour

- Entry: **Manage** on the Cells panel head when cells are loaded.
- Close: Esc, backdrop click, or Close.
- Edits reuse existing APIs (`POST /api/cells/{id}/update`, select-all, delete, clear) via Alpine `updateCell` / `selectAll` / `removeCell` / `clearAll` — no new persistence model.
- Table fields: selected, label, group, mass, area, nominal capacity (with
  per-row unit), **basis** (`nom_cap_specifics`: gravimetric / areal / absolute),
  cycle mode (anode/cathode/full_cell), cycles (read-only), remove.
- Physical edits (`mass` / `area` / `nominal_capacity` / `nom_cap_specifics` /
  `cycle_mode`) go through `POST /api/cells/{id}/update` → `Library.update` →
  adapter `apply_physical_meta` (attribute assign + full `make_summary()`).
  Persist via project `.cellpy` save (not the org-only manifest). See #69 / #86.
- Basis defaults from cellpy meta per cell; nom. cap unit hint follows basis
  (mAh/g / mAh/cm² / mAh).
- Client-only niceties: filter by label, sort by group/name, select-by-group (sequential updates; replot once at end).
- **Export ▾** (issue #28): exports **selected** cells via cellpy `save` / `to_csv` / `to_excel`
  (`POST /api/export/cells?fmt=cellpy|csv|xlsx`). One cellpy/xlsx file is returned bare;
  csv (multi-file) and multi-cell exports are zipped. Reuses `download()` (desktop Save As).

## UI location

- Markup: `web/templates/index.html` (modal after `.layout`)
- Logic: `web/static/js/app.js` (`cellsManagerOpen`, `filteredSortedCells`, …)
- Styles: `web/static/css/app.css` (`.modal-*`, `.cells-table`) using existing theme tokens
