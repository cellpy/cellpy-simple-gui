# Status — #174 open project: replace vs append

- [x] Done

## What was done

- `projects.open_project(..., mode="replace"|"append")` (`projects.OpenMode`).
  Replace clears first (unchanged behaviour). Append keeps the loaded cells
  and current project association, offsets the incoming group numbers by
  `Library.group_offset_for_append()` (highest group in use) and moves group
  names (#187) with them. Append into an empty library behaves like an open.
- `POST /api/projects/open` and `POST /api/projects/load-journal` accept
  `mode` (default `replace`). The open job reports `action: opened|appended`.
  The journal job clears the library only after the journal yielded cells
  (corrupt / empty journal never wipes the loaded set) and offsets groups on
  append. cellpy project config is switched only when actually replacing.
- UI: "Append to the loaded cells" checkbox in the Project panel (shown when
  cells are loaded); Open / Open path buttons read Append / Append path while
  on; replacing a non-empty library asks for confirmation (notes unsaved
  changes). Toast "Appended … added to the loaded cells"; append marks the
  set dirty. The journal tab of *Add cells…* always appends.
- README ("Projects on disk") and the design doc
  `project-refresh-and-import.md` describe both modes.

## Tests

- `tests/test_projects.py`: replace default; append keeps cells, renumbers
  groups, carries names, keeps the project association; append into empty;
  `group_offset_for_append`; API `mode` (append → groups 4/5, replace, 422
  on unknown mode).
- `tests/test_journal.py`: journal append renumbers groups; replace is the
  default; corrupt journal under replace keeps the library.
- `tests/test_gui_playwright.py` (e2e): Append toggle → no confirm, two
  cells, distinct groups, dirty tag; Open → confirm text, one cell.

Full suite `uv run pytest -q -p no:warnings` green (4 skips).

## Remaining

Nothing for this issue.
