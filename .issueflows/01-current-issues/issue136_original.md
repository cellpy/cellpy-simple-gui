# Issue #136: Redesign the loading surface: one "Add cells" flow, staged file list, contextual help

Source: local number chosen by the owner (2026-10-01). **Not a GitHub issue:**
[cellpy/cellpy-simple-gui#136](https://github.com/cellpy/cellpy-simple-gui/pull/136)
is the merged container-image PR. No GitHub issue for this work existed when
the build started (`gh` is read-only for the cloud agent); the body below is
ready to paste when one is created, and `iflow close` should reference that
number in the PR instead of `#136`.

## Original issue text

### Problem / context

Loading data is spread over two sidebar panels and five different entry points
that evolved issue by issue (#75 projects/journals, #133 upload, #160/#162
remote URIs and remote find, #143 instrument availability):

- **Project** panel: *Open a project…* dropdown, *Save*, *Close*, and a second
  row for `project.json` / batch-journal / folder paths — two rows that both
  open projects, six glyph-only buttons (↥ ↻ ⤓ ✕ 📁 ↧).
- **Data** panel: three stacked disclosures (*Load demo cells*, *Add cellpy
  files*, *Import raw instrument files*), each with its own nested
  *Find in a remote folder…* disclosure.

Measured in server mode at 1440×900 with every disclosure open: the **Data**
panel is ~1680 px tall, the sidebar scrolls to ~2220 px inside an 844 px
viewport, and the sidebar holds **13 hint paragraphs** and **8 free-text
inputs**. Concretely:

1. All file sources (Browse, remote Find, upload, typed globs) collapse into a
   single `a; b; c` text field; the user can see one path at a time and never
   sees what a glob will expand to before pressing Load.
2. Help text is always-on and repeated (six lines of SFTP / `.env_cellpy` /
   Arbin-HDF5 caveats under *Add cellpy files*, repeated under *Import raw*).
3. The primary action differs per form: demo = primary button duplicating the
   disclosure header; cellpy files = ghost *Load files* sharing a row with
   *max*; raw = primary *Import & process* below the remote-find block.
   Disabled buttons give no reason.
4. Desktop vs served mode changes the form shape (📁 appears/disappears, an
   upload input appears above the path field) instead of one adaptive input.
5. Progress lives in a separate block between Data and Cells with an ellipsised
   message; results are toasts that disappear; nothing remembers recent paths,
   remote folders or journals.
6. After a load the Data panel keeps its full height while the Cells list is
   floored at 220 px, although loading is a start-of-session activity.

### Spec

One coherent redesign (single PR), staged so each stage is independently
shippable and testable:

1. **Sidebar restructure.** Project panel = current project (name + saved/dirty
   tag), **Open** (projects dropdown + `project.json`/folder path + Browse),
   **Save**, **Close**, with text labels instead of glyph-only buttons. Data
   panel = one **Add cells…** button that opens a modal, plus a one-click
   **Load demo cells** button (no disclosure). After a successful load the Data
   panel collapses to the single *Add cells…* line.
2. **"Add cells" modal** (centred, same chrome as *Manage cells*) with a
   source switcher: **cellpy files · Raw instrument files · Batch journal**.
   One form visible at a time; raw import gets a two-column layout (source
   left, processing options right); each form ends with exactly one full-width
   primary button with a dynamic label (*Load 3 cellpy files*, *Import 2 raw
   files with Arbin (res)*) and an inline reason when disabled.
3. **Staged file list** replacing the semicolon string: one row per file
   (name, type badge, remove, exists/unsupported flag), fed by Browse, drop /
   upload, pasted paths or globs (expanded server-side into the list as a
   preview before loading), and remote Find. *max* becomes "showing 10 of 23
   matches".
4. **Adaptive source input**: a single *Drop files here · Browse… · or paste a
   path* zone that routes to native pick (desktop), `/api/upload` (served), or
   the staged list (typed), using the existing `canPick` / `hostPathsAllowed`
   capabilities.
5. **Contextual help**: hints shown only when relevant (SFTP/credential hint
   when a path matches `^(sftp|ssh|scp)://`; Arbin-HDF5 hint when a `.h5` is
   staged under cellpy files; instrument-unavailable warning inline). Target
   ≤ 4 visible hints in the default state.
6. **Results and recents**: inline progress under the pressed button, a
   persistent *Loaded 3 cells · 1 skipped* summary with expandable errors
   until the next action, and a *recent* menu per input (paths, remote
   folders, journals; `localStorage`, max 8).

No new cellpy calls; no change to load/ingest/project job semantics or to the
`{added, errors, notes}` / `{paths, total, …}` result shapes. One small new
read-only endpoint for glob preview is acceptable if it reuses
`core/files.expand_paths`.

### Acceptance criteria

- [ ] Default sidebar (no cells) fits in a 900 px-high viewport without
      scrolling; no disclosure stacks remain in the Data panel.
- [ ] Every loading route still works end to end in **both** modes:
      desktop/loopback (host paths + native pick) and served
      (`hostPathsAllowed=false`: upload only, host paths refused with the
      existing wording).
- [ ] Files from Browse, upload, pasted path/glob and remote Find all land in
      the staged list; the user can remove rows before loading; glob preview
      respects `effective_max_files` and shows total vs. shown.
- [ ] Each form has exactly one primary button; its label reflects the staged
      count; when disabled, a visible reason is shown next to it.
- [ ] ≤ 4 `.hint` elements visible in the default state; SFTP and Arbin-HDF5
      hints appear only in their trigger conditions.
- [ ] After a load: result summary visible without a toast; Data panel
      collapsed; Cells list gets the freed height.
- [ ] Recent entries survive a reload and are capped at 8 per input.
- [ ] `uv run pytest` green (full suite), including
      `test_app_js_parses`, `test_index_alpine_state_is_defined`, and the
      new static/API tests from the plan; `uv run pytest -m e2e` green with
      Chromium (existing *Load demo cells* smoke kept working by keeping that
      accessible button name).
- [ ] README *Quick start*, *Remote files (SSH / SFTP)* and
      `docs/deployment.md` *Upload from the browser* updated to the new
      labels; design note added under `.issueflows/04-designs-and-guides/`.

### Out of scope

- New data sources, new instruments, or changes to cellpy loading semantics.
- SFTP folder browser, served-mode remote allow-list, GUI credential editor
  (still deferred per `otherpath-remote-loading.md`).
- Manage-cells modal, plotting panes, export.
- Resizable or collapsible sidebar as a whole (only the Data panel collapses).
- Auto-watching the projects directory.
