# Issue #75: Refresh project list and open portable projects from the import path

Source: https://github.com/cellpy/cellpy-simple-gui/issues/75

## Original issue text

### Problem / context
Portable app projects live under `~/.cellpy_simple_gui/projects/` and only show up in the Open dropdown after a list refresh (currently on init / save / open / journal load). If the user copy-pastes a project folder into that directory while the app is running, there is no way to refresh the list. Separately, the “Load a native cellpy batch journal” control only accepts batch journals — it cannot open a `cellpy-simple-gui` project folder (`project.json` + `data/*.cellpy`), even though `resolve_project_path` / `open_project` already support absolute project paths.

### Spec
1. **Refresh projects list** — Add a small control next to the Open dropdown (e.g. refresh icon/button) that calls the existing `GET /api/projects` / `refreshProjects()` so newly copied folders appear without restarting the app. Keep behaviour when the list is empty (show the control even if `projects.length === 0`, or always show Open+refresh).
2. **Import portable projects** — Extend the journal/import row so it can also load a **cellpy-simple-gui project**:
   - Accept a path to a project folder (or its `project.json`).
   - Detect portable project vs batch journal (e.g. directory with `project.json`, or a `project.json` file).
   - Portable project → same path as Open (`/api/projects/open` with absolute path); journal → existing `load-journal`.
   - Update copy/hints/picker so users know both kinds are supported (browse may need a folder pick or “project.json / journal.json” file filter where the desktop picker allows).
3. Prefer reusing `open_project` / `resolve_project_path` — no second persistence format.

### Acceptance criteria
- [ ] After copying a valid project into `…/projects/`, Refresh updates the Open dropdown without restart.
- [ ] Importing a portable project path (folder or `project.json`) loads cells and sets current project like Open from the dropdown.
- [ ] Batch journal import still works unchanged for real journals.
- [ ] Clear error if the path is neither a valid project nor a loadable journal.
- [ ] `uv run --extra dev pytest` still passes (add a light detect/open test if easy).

### Out of scope
- Watching the projects directory for auto-refresh
- Importing zip archives
- Moving/copying external projects into `projects_root` automatically (opening via absolute path is enough unless we decide otherwise in plan)
