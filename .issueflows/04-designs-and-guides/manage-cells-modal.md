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

## Group names (issue #187)

- Names are **library-level** (`Library._group_labels`, keyed by group number),
  not a per-cell field: cells move between groups, the name stays with the
  number. `all()` stamps a `CellRecord.group_label` snapshot so `collect._batch`
  and `CellMeta` see it without threading a map through every collector.
- Only names the user (or a journal / manifest) chose are stored; blank or the
  default spelling `group <n>` removes the entry. Names of groups with no cells
  are kept in memory (cells may move back) but not reported by `groups()` /
  `group_labels()`, so they are not saved.
- Plots: cellpy already names group-averaged traces after `group_labels`;
  per-cell traces of a named group get a Plotly `legendgrouptitle` from
  `collect.group_titles(records)` (only for named groups — a bare number adds
  nothing the swatch does not).
- Persistence: `project.json` → `groups: [{id, label}]` (optional). Journals →
  the `group_label` column of `journal.pages` via `cellpy_adapter.load_journal`.
- UI: the *Groups* strip above the table (`.mgr-groups`, one `.mgr-group` chip
  per group in use); `renameGroup()` → `POST /api/groups/{id}` → `_applyState`
  → `_replotAfterEdit()` (same deferred redraw as other modal edits).
- Alternatives considered: a `group_label` column on each cell row (drifts as
  soon as two cells disagree) and a separate "Groups" modal (one more dialog
  for a one-field edit).

## UI location

- Markup: `web/templates/index.html` (modal after `.layout`)
- Logic: `web/static/js/app.js` (`cellsManagerOpen`, `filteredSortedCells`, …)
- Styles: `web/static/css/app.css` (`.modal-*`, `.cells-table`) using existing theme tokens
