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
