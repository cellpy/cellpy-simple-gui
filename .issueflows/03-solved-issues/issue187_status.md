# Status — #187 name of groups

- [x] Done

## What was done

- `Library` keeps custom group names (`set_group_label`, `group_label`,
  `group_labels`, `groups`); `all()` stamps `CellRecord.group_label` so the
  collectors and `CellMeta.group_label` see the name without extra plumbing.
  `clear()` forgets the names.
- `collect._batch` hands cellpy the effective name (`custom` or `group <n>`),
  so group-averaged traces are named after it. New `collect.group_titles()` +
  `figure_json(group_titles=…)` caption per-cell traces of a named group with
  a Plotly `legendgrouptitle` (summary + cycles pane).
- API: `/api/state` carries `groups`; `POST /api/groups/{group}` with
  `{"label": …}` names a group (blank → default) and returns the state.
- Persistence: `ProjectManifest.groups` (`[{id, label}]`, optional, so older
  manifests still open) is saved from the in-use named groups and restored on
  open. `cellpy_adapter.load_journal()` returns `(cells, group_labels)` read
  from the journal's `group_label` column (cellpy's `group <n>` placeholders
  dropped); `load_journal_cells()` stays as a wrapper; the journal job applies
  the names.
- UI: a *Groups* strip at the top of the Manage cells modal (swatch, number,
  editable name with `group <n>` placeholder, cell count). Renames follow the
  deferred-replot rule from #184. Group inputs in the sidebar and table show
  the group name as a tooltip. State writes go through `_applyState()`.
- Docs: README feature list / project layout mention group names;
  `llms-full.txt` regenerated.

## Tests

- `tests/test_core.py`: library group-name semantics; names reach the
  grouped legend; legend-group titles on ungrouped summary and cycles plots.
- `tests/test_projects.py`: save → open round trip; manifest without `groups`.
- `tests/test_journal.py`: `group_label` column read (and absent); journal job
  applies the names end to end via the API.
- `tests/test_api.py`: `/api/groups/{group}` + state shape.
- `tests/test_gui_playwright.py` (e2e): naming and un-naming a group in the
  modal, legend caption after close.

Full suite: `uv run pytest -q -p no:warnings` green (3 skips, example data).

## Remaining

Nothing for this issue. Appending a journal whose group numbers collide with
groups already in the library overwrites those groups' names — the general
replace-vs-append question is #174.
