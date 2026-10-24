# Project list refresh + portable import (#75)

## Context

Projects under `~/.cellpy_simple_gui/projects/` only appeared in the Open
dropdown after init/save/open/journal. Copy-paste into that folder while the
app was running left no refresh control. The journal import row could not open
portable app projects even though `open_project` already accepts absolute paths.

## Decision

- Always show the Open row; add **↻** → `GET /api/projects` / `refreshProjects()`.
- `classify_import_path` (filename/dir only): dir/`project.json` → project;
  other file → journal. Exposed as `POST /api/projects/classify-import`.
- `resolve_project_path` accepts a `project.json` file path (uses parent).
- Import UI routes to `/api/projects/open` or `load-journal`; one desktop
  browse control for JSON (`project.json` or batch journal). Paste a folder
  path to open a portable project directory.
- Do not auto-copy external projects into `projects_root`.

## Alternatives considered

- Client-only path heuristics — rejected; need FS existence checks on the server.
- Auto-watch projects directory — out of scope.

## Open mode: replace vs append (#174)

- Every open — saved project, `project.json` / folder path, batch journal —
  carries a `mode`: **`replace`** (default; clears the library first, as the
  project open always did) or **`append`**. `projects.OpenMode`, accepted by
  `POST /api/projects/open` and `POST /api/projects/load-journal`.
- **Append** keeps the loaded cells and the current project association
  (Save still goes to the project that was open; the appended set is marked
  dirty). Incoming group numbers are offset by `Library.group_offset_for_append()`
  (= highest group in use), so a second project's group 1 becomes `max + 1`
  and its internal grouping is preserved; group names (#187) move with the
  numbers. Appending into an empty library is just an open.
- **Replace** for journals clears the library only after the journal produced
  cells, so a corrupt or empty journal cannot wipe the loaded set. It also
  drops the active project's cellpy config (the project is gone).
- cellpy project config (`cellpy.toml`) is only switched when the open actually
  replaces; an append reads the incoming cells under the *current* project's
  settings. Known limitation: cells from a project pinned to different
  settings are appended under the open project's settings.
- UI: one checkbox in the Project panel ("Append to the loaded cells", shown
  once cells exist) drives both Open controls; the buttons read "Append" /
  "Append path" while it is on. Replacing a non-empty library asks for
  confirmation (mentions unsaved changes when dirty). The journal tab of the
  *Add cells…* modal always appends — "add" is its whole point.
- Alternatives considered: separate Open / Append buttons (crowds the sidebar
  rows); a replace-or-append prompt on every open (one more dialog on the
  common path, and it still would not explain the group renumbering).
