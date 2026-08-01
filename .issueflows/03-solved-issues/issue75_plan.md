# Plan — Issue #75: Refresh project list + import portable projects

## Goal

Let users refresh the Open-project dropdown after copy-pasting into `…/projects/`, and let the existing journal import row open a portable `cellpy-simple-gui` project (folder or `project.json`) as well as a batch journal.

## Constraints

- Reuse `open_project` / `resolve_project_path` — no second persistence format; do not auto-copy into `projects_root`.
- Out of scope: directory watching, zip import.
- Desktop pickers stay behind `canPick` / `POST /api/system/pick`; typed paths must work in `--server` mode too.
- Match existing Project sidebar patterns (ghost buttons, hints).

### Prior art

- [`projects.list_projects`](../../src/cellpy_simple_gui/core/projects.py) / `GET /api/projects` + UI [`refreshProjects()`](../../src/cellpy_simple_gui/web/static/js/app.js) — refresh is already implemented; only missing a button. Open row currently `x-show="projects.length"` (hides when empty).
- [`projects.resolve_project_path`](../../src/cellpy_simple_gui/core/projects.py) — absolute **directory** with `project.json`, or slug under `projects_root`. Does **not** yet accept a path to the `project.json` file itself.
- [`openProject` / `loadJournal`](../../src/cellpy_simple_gui/web/static/js/app.js) → `/api/projects/open` vs `/api/projects/load-journal`.
- [`POST /api/system/pick`](../../src/cellpy_simple_gui/api/routers/system.py) — `kind=journal` → `FileDialog.OPEN`, `*.json`; design note [`pywebview-file-dialog.md`](../04-designs-and-guides/pywebview-file-dialog.md) allows `FileDialog.FOLDER` when needed.
- Tests: [`tests/test_projects.py`](../../tests/test_projects.py) (`temp_projects_root`, save/open round-trip, API open).
- Toolbox: none relevant.
- Graph: project persistence already covered by existing modules; no new god-node dependency.

## Approach

1. **Refresh UI** — Always show the Open row (dropdown + open button), even when `projects.length === 0`. Add a refresh ghost button that calls `refreshProjects()` (and optionally selects the newest slug if current `openTarget` vanished). Title: “Refresh project list”.

2. **Detect import kind** — Add `projects.classify_import_path(path: str) -> Literal["project", "journal"]` (or raise `ValueError` with a clear message):
   - Directory containing `project.json` → `"project"`
   - File named `project.json` → `"project"` (resolve to parent)
   - Existing file otherwise → `"journal"` (batch journal; cellpy will validate)
   - Missing / empty / other → `ValueError`

3. **`resolve_project_path`** — If `path` is a file and `name == "project.json"`, use `path.parent` when that dir is a project. Keeps absolute-folder open working as today.

4. **UI import row** — Rename placeholder/hint to cover both (e.g. “project folder, project.json, or batch journal”). Change `loadJournal()` → `loadImportPath()` (or keep name, branch inside):
   - classify → project: `runJob("/api/projects/open", { target: resolvedPath })` then refresh
   - classify → journal: existing `load-journal` path
   - On classify error: `notify("error", …)` without starting a job  
   Prefer a tiny `POST /api/projects/classify` **or** classify in the client only for obvious cases and let the server do authoritative classify in a thin wrapper — **recommend**: pure Python helper used by a small endpoint or by the client calling open/load-journal after local heuristics. Simplest ship: **client-side heuristics matching the helper rules** (dir / `project.json` file) + server `resolve_project_path` fix; journal stays server-validated. Optionally expose `classify_import_path` only in tests/core without a new API.

5. **Picker** — Keep file browse (`kind=journal`, widen label to mention project.json). Add `kind=folder` using `webview.FileDialog.FOLDER` (single path) for “Browse folder…” next to the import row when `canPick`. Folder path fills the field; user clicks load (or auto-load like today’s journal pick — **recommend auto-load on pick**, same as `pickJournal`).

6. **Design note** — Short `.issueflows/04-designs-and-guides/` entry: refresh control + import detect rules + folder pick kind.

## Files to touch

| Path | Change |
|------|--------|
| `src/cellpy_simple_gui/core/projects.py` | `classify_import_path`; extend `resolve_project_path` for `project.json` file |
| `src/cellpy_simple_gui/api/routers/system.py` | `kind=folder` → `FileDialog.FOLDER`; tweak journal file-type label |
| `src/cellpy_simple_gui/web/templates/index.html` | Always-show Open row + refresh; import hint/placeholder; folder browse button |
| `src/cellpy_simple_gui/web/static/js/app.js` | `loadImportPath` / pick folder; wire refresh |
| `tests/test_projects.py` | classify + open via absolute path / `project.json` file; list after “copy” |
| `.issueflows/04-designs-and-guides/` | Brief decision note |
| `.issueflows/04-designs-and-guides/pywebview-file-dialog.md` | Add `FOLDER` row for `kind=folder` |

## Test strategy

- `uv run --extra dev pytest`
- Unit: `classify_import_path` for dir / `project.json` file / plain json file / missing
- Unit: `open_project` with absolute path outside `projects_root` and with `…/project.json` file path
- Unit/API: after writing a new project folder into `temp_projects_root`, `list_projects` / `GET /api/projects` includes it (documents refresh data path)
- Existing save/open/API tests still pass

## Open questions

1. **Auto-load on folder pick** — recommend yes (match `pickJournal`). Prefer fill-only?
2. **Ambiguous `.json` that isn’t `project.json`** — treat as journal (cellpy errors if wrong). Or sniff `schema_version` + `cells[].data_file` first? Recommend **filename/dir rules only** for MVP.
3. **Empty Open row** — recommend always show dropdown + refresh + open (open stays disabled until a selection). Agree?
