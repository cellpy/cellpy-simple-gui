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

## Plot refresh timing (issue #184)

- Edits made **inside the modal** do not redraw the chart. `updateCell` /
  `selectAll` / `removeCell` / `selectGroup` go through `_replotAfterEdit()`,
  which only flags `_replotOnClose` while `cellsManagerOpen`; `closeCellsManager()`
  then calls `replotCurrent()` once. The footer says so ("Plots refresh when
  this dialog closes." / "Edits saved — …"). Sidebar edits still redraw at once.
- **Stale plot responses are dropped.** Each chart (`summary` / `cycles` /
  `cell`) carries a request sequence (`_plotSeq`); `_fetchFigure` returns `null`
  for a response overtaken by a newer request, so a burst of edits no longer
  replays every intermediate figure. `plotBusy` is backed by an in-flight
  counter (`_plotInflight`), so the spinner stays until the last request settles.
- Alternatives considered: debouncing per-edit requests (still redraws while
  the modal covers the chart; timing-dependent) and cancelling in-flight
  fetches with `AbortController` (the server would keep computing the figure
  anyway; sequence numbers give the same visible result with less machinery).

## UI location

- Markup: `web/templates/index.html` (modal after `.layout`)
- Logic: `web/static/js/app.js` (`cellsManagerOpen`, `filteredSortedCells`, …)
- Styles: `web/static/css/app.css` (`.modal-*`, `.cells-table`) using existing theme tokens
