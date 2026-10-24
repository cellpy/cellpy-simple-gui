# Issue #136 — Plan: redesign the loading surface (files, projects, journals, raw import)

> Written against `main` @ `e056abe`; accepted by the owner 2026-10-01 ("all
> can be combined into one issue", local number 136 — see
> [`issue136_original.md`](issue136_original.md) for the GitHub caveat).

## Goal

Replace the five scattered loading entry points (two Project rows, three Data
disclosures with nested remote-find blocks) with one **Add cells** modal fed by
a **staged file list**, a compact Project panel with labelled verbs, contextual
help instead of thirteen always-on hints, inline results, and remembered
recent sources — without changing any load / ingest / project job semantics.

## Constraints

- **cellpy boundary** unchanged: no new cellpy import; routers and UI deal in
  strings. The only backend addition is a read-only preview endpoint that
  wraps the existing `core/files.expand_paths` (see Approach §3).
- **Policy gates unchanged**: `hostPathsAllowed` (#120/#133) and
  `remote_paths_allowed()` (#160) keep deciding what the UI offers; served
  instances must still refuse host paths and remote URIs with the existing
  wording. The redesign may hide controls but never relax a refusal.
- **Job contract unchanged**: `runJob` / `streamJob` / `reportJobResult`
  keep consuming `{added, errors, notes}` and `{paths, total, errors, notes}`;
  the single job bar remains the only progress source of truth
  (`job.active` still locks the loading UI).
- **Existing e2e anchors stay valid**: `tests/test_gui_playwright.py` clicks
  `get_by_role("button", name="Load demo cells")` and waits for `.cell-card`,
  `.job-msg`, `.job`, `#summaryChart`. Keep that accessible name and those
  selectors (the demo button moves, its name does not).
- **Static frontend tests stay meaningful**: `test_index_alpine_state_is_defined`
  requires every `x-model` root to be declared in `app()`; new state
  (`addCells`, `staged`, `recent`, `lastResult`) must be declared at the top of
  the component, not created lazily.
- **One PR**, staged so each stage leaves the app usable (see Test gates —
  every stage ends in a green run, never a "fix it in the next stage").
- **Out of scope** (issue text): new sources/instruments, SFTP browser,
  served-mode remote allow-list, credential editor, Manage-cells, plots,
  export, whole-sidebar resizing, projects-dir watching.
- Design docs to follow / update:
  [`manage-cells-modal.md`](manage-cells-modal.md) (modal chrome, Esc /
  backdrop / Close behaviour), [`project-refresh-and-import.md`](project-refresh-and-import.md)
  (classify-import routing), [`otherpath-remote-loading.md`](otherpath-remote-loading.md)
  (Find populates a review list before Load — generalised here),
  [`job-cancel-dismiss.md`](job-cancel-dismiss.md), [`this-project.md`](this-project.md).

### Prior art

- [`web/templates/index.html`](../../src/cellpy_simple_gui/web/templates/index.html):
  Project panel (`.proj-open`, `.proj-save`, `journalPath` row), Data panel
  (`showDemo` / `showLoadFiles` / `showImport` disclosures, `remoteFind.load` /
  `remoteFind.ingest` sub-disclosures), `.job` block, Manage-cells modal
  markup (`#cells-manager-title`, `.modal`, `.modal-title`) — reuse the modal
  shell verbatim for *Add cells*.
- [`web/static/js/app.js`](../../src/cellpy_simple_gui/web/static/js/app.js):
  `loadFiles` / `ingestRaw` split the text field on `;` → both become
  consumers of the staged list; `uploadAndLoad` already hands server paths to
  `/api/load/files` (same road for staged uploads); `pick(kind, assign)` and
  `_applyRemoteFind` assign joined strings → assign into the staged list
  instead; `reportJobResult` → also writes `lastResult`; `openCellsManager`
  shows the modal open/close + Esc pattern.
- [`web/static/css/app.css`](../../src/cellpy_simple_gui/web/static/css/app.css):
  `.disclosure`, `.import-form`, `.remote-find`, `.grid2`, `.chips`,
  `.job*`, `.modal*`, `.cells-table` (dense table styling to mirror for the
  staged list).
- [`core/files.py`](../../src/cellpy_simple_gui/core/files.py):
  `expand_paths(patterns, max_files) -> Expansion{paths, errors, notes}` and
  `effective_max_files` — the preview endpoint is a thin wrapper; `is_glob`
  tells the UI whether a row needs expansion.
- [`core/projects.py`](../../src/cellpy_simple_gui/core/projects.py)
  `classify_import_path` + `POST /api/projects/classify-import` — existing
  server-side existence check pattern; the Batch-journal tab keeps using it.
- [`api/routers/system.py`](../../src/cellpy_simple_gui/api/routers/system.py)
  `/system/capabilities` (`can_pick`, `host_paths_allowed`, `max_upload_mb`,
  `max_files`) — all the flags the adaptive source zone needs already exist.
- [`api/routers/uploads.py`](../../src/cellpy_simple_gui/api/routers/uploads.py)
  `/upload` → `{saved:[{path,…}], errors}` — drop-zone uploads reuse it.
- Tests to mirror: `tests/test_api.py::test_app_js_parses`,
  `::test_index_alpine_state_is_defined` (static template/JS contract),
  `tests/test_files.py` (expand_paths cases), `tests/test_uploads.py`
  (`served` fixture), `tests/test_remote_find.py`,
  `tests/test_gui_playwright.py` (`live_server` + `browser_page` fixtures).
- Toolbox `.issueflows/00-tools/`: README only — nothing to reuse. Graph:
  communities 83 (`expand_paths`), 245 (ingest jobs), 252 (projects),
  255 (system pick) confirm the touched surface is template → app.js →
  existing routers; plots / library untouched.

## Approach

Six stages, in this order. Each stage is a separate commit and ends with its
test gate (see *Test gates*). Stages 1–2 are template/CSS/JS only; stage 3
adds the one endpoint; 4–6 are JS/CSS; 7 is docs.

### Stage 1 — Sidebar restructure (template + CSS)

- **Project panel** → three rows with text labels: *(a)* current project
  (`projectTagLabel`, saved/dirty, `cellpy.toml` tag) ; *(b)* **Open**:
  projects `<select>` + `Open` button + `↻`, and beneath it the path field
  (`journalPath`) + `Browse…` (`canPick`) + `Open path` ; *(c)* **Save**:
  name input + `Save` + `Close`. Buttons get `aria-label`s equal to their text.
- **Data panel** → `Load demo cells` (primary, `btn-primary block`, same
  accessible name as today) and `Add cells…` (`btn block`, opens the modal).
  Remove the three disclosures and both `remoteFind.*.open` toggles from the
  sidebar; the forms move into the modal in stage 2 (during stage 1 the old
  forms stay in place behind the `Add cells…` button area so the app remains
  usable — stage 1 only rewrites the Project panel and the Data panel header;
  the disclosures are deleted at the end of stage 2).
- **Collapse after load**: new state `dataCollapsed` (default `false`); set
  `true` in `refreshState()` when `cells.length > 0`; the Data panel renders
  only the `Add cells…` line when collapsed, with a `▸` to expand. `Cells`
  panel keeps `.panel.grow`.

### Stage 2 — "Add cells" modal with source switcher

- New state `addCells: { open: false, tab: "cellpy" | "raw" | "journal" }`,
  `openAddCells(tab = "cellpy")`, `closeAddCells()`. Esc / backdrop / Close
  mirror `openCellsManager`. Opening is blocked while `job.active`.
- Modal body: segmented control (three `<button role="tab">`), one
  `<section role="tabpanel">` per tab:
  - **cellpy files**: source zone (stage 4) → staged list (stage 3) → footer.
  - **Raw instrument files**: two columns. Left: source zone + staged list.
    Right: *Instrument*, *Format / model*, `grid2` of Mass / Area / Nom. cap /
    Specifics, *Cycle mode* (all existing `ingest.*` bindings). Below both: the
    *try a bundled raw file* chips.
  - **Batch journal**: path field (`journalPath`) + Browse + `Open journal`;
    note that `project.json`/folders belong to Project → Open (the
    `classify-import` call still routes either way, so a pasted `project.json`
    keeps working).
- **Footer** (every tab): one `btn-primary block` with a dynamic label
  (`addCellsPrimaryLabel` getter: `Load 3 cellpy files`, `Import 2 raw files
  with Arbin (res)`, `Open journal`), and a `.hint.reason` next to it when
  disabled (`addCellsDisabledReason` getter: `Add at least one file`,
  `Instrument unavailable — <reason>`, `A job is running`).
- Remove the sidebar disclosures, `showDemo` / `showLoadFiles` / `showImport`
  and `remoteFind.*.open` state (remote-find lives in the source zone, stage 4).

### Stage 3 — Staged file list + glob preview endpoint

- Backend: `POST /api/files/preview` in
  [`api/routers/cells.py`](../../src/cellpy_simple_gui/api/routers/cells.py)
  (same token guard): body `{patterns: list[str], max_files: int}` →
  `expand_paths(patterns, effective_max_files(max_files))` →
  `{paths, errors, notes, total}` where `total` is the pre-cap match count
  (add it to `Expansion` or compute in the router from the truncation note —
  prefer a small `Expansion.total` field with a default so existing callers
  are untouched). Served-mode refusals and remote-URI passthrough are inherited
  from `expand_paths` unchanged; remote URIs are returned as-is with no
  existence check (there is none locally).
- Frontend state: `staged: { cellpy: [], raw: [] }`, rows
  `{ path, name, ext, source: "pick"|"upload"|"typed"|"remote"|"glob",
  status: "ok"|"missing"|"unsupported"|"remote" }`.
  Helpers: `stage(kind, paths, source)`, `unstage(kind, idx)`,
  `clearStaged(kind)`, `stagedCount(kind)`.
- Typed input: an `<input type="text">` per tab with `Add` (and Enter). A
  literal path or `;`-separated list → `/api/files/preview` → rows with
  `status` from `errors`; a glob → the same call → rows tagged `glob`, plus a
  banner `Showing 10 of 23 matches — raise "max" or narrow the pattern` when
  `total > paths.length`. The *max* numeric input moves next to `Add`.
- `loadFiles()` / `ingestRaw()` read `staged[kind].map(r => r.path)` and
  `max_files: paths.length` (the preview already applied the cap); on success
  `clearStaged(kind)` and close the modal; on partial errors keep the failing
  rows and mark them.
- Supported-extension check is client-side and advisory: cellpy tab accepts
  `.cellpy` / `.h5` / `.hdf5` (others → `unsupported`, still loadable, with
  the Arbin-HDF5 hint); raw tab uses `currentInstrument().suffixes` when
  present.
- `_applyRemoteFind(r)` → `stage(target, r.paths, "remote")` plus the same
  total/shown banner (replaces writing into the text field).
- Table styling mirrors `.cells-table` (dense rows, `×` per row, badge per
  `status`), max-height with internal scroll so the modal never exceeds the
  viewport.

### Stage 4 — Adaptive source zone (drop / browse / paste)

- One `.source-zone` component per tab (cellpy, raw): text *Drop files here*,
  `Browse…` button (`x-show="canPick"` → `pick(kind, p => stage(kind, p,
  "pick"))`), `Upload…` file input (`x-show="!hostPathsAllowed"`, reuses
  `uploadAndLoad` split into `uploadOnly(files) → saved paths → stage(kind,
  …, "upload")`), the typed path row from stage 3, and *Find in a remote
  folder…* as a small disclosure inside the zone (`x-show="hostPathsAllowed"`,
  existing `remoteFind[target].dir/filter` + `findRemote(target)`).
- Drag-and-drop: `@dragover.prevent`, `@drop.prevent="onDrop(kind, $event)"`.
  Served mode → `uploadOnly(event.dataTransfer.files)`. Desktop → if the
  dropped `File` objects expose a full path (pywebview ≥ 5 adds
  `pywebviewFullPath`; **verify in the spike at the start of this stage**)
  stage those paths; otherwise fall back to the upload path (a loopback
  desktop instance also allows uploads, so nothing is lost — it just copies).
- The old upload field above the path input and the two 📁 pick buttons in the
  sidebar are removed (their functions now live in the zone).

### Stage 5 — Contextual help, inline results, recents

- **Hints**: keep one short line per form; conditional hints as `x-show`
  getters — `showsRemoteHint(kind)` (any staged/typed path matching
  `^(sftp|ssh|scp)://`), `showsH5Hint` (a `.h5` staged in the cellpy tab),
  instrument-unavailable (existing). Target ≤ 4 `.hint` visible in the default
  sidebar + modal state; assert this in a static test (Stage 5 gate).
- **Inline progress**: the footer primary button shows the spinner +
  `job.message` while `job.active && addCells.open`; the sidebar `.job` block
  stays (it is also the e2e anchor) but gains a `kind` badge.
- **Results**: `lastResult: { kind, added, errors, notes, at }` written in
  `reportJobResult`; rendered as a dismissible `.result-card` in the modal
  footer and, when the modal is closed, under the Data panel header
  (`Loaded 3 cells · 1 skipped ▸ details`). Toasts keep firing for errors only
  (`ok` toasts become redundant and are dropped for load/ingest jobs).
- **Recents**: `recent: { cellpy: [], raw: [], journal: [], remoteDir: [] }`
  persisted in `localStorage["csg.recent"]`; `remember(kind, value)` on each
  successful load / find; capped at 8, most-recent first; rendered as a
  `<datalist>` on the typed inputs and as a small ▾ menu on the Project path
  field. Cleared from the Diagnostics modal (dev mode) — optional.

### Stage 6 — Docs and design record

- README: *Quick start* (still "click **Load demo cells**"), *Features*
  bullets naming *Add cells…*, *Remote files (SSH / SFTP)* ("Find in a remote
  folder… inside Add cells → matches appear in the file list"), and
  `docs/deployment.md` *Upload from the browser* (now *Add cells → Drop or
  Upload*). Regenerate `llms*.txt` (`uv run tools/gen_llms_txt.py`) — note the
  baseline already fails `test_llms_full_txt_is_current` after the README
  icon commit on `main`; this stage fixes it as a side effect.
- Add `.issueflows/04-designs-and-guides/loading-ui.md` (decision record:
  modal + staged list + adaptive zone; alternatives: sidebar segmented
  control, keep the `;` string, drawer) and update
  `otherpath-remote-loading.md` §UX ("Find populates the staged list").
- Issue files already live under `01-current-issues/issue136_*` (captured
  2026-10-01); `iflow close` moves them to `03-solved-issues/`.

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/web/templates/index.html` | Project panel rows with labels; Data panel → demo + *Add cells…*; new `#add-cells` modal (tabs, source zone, staged table, footer); remove disclosures; conditional hints; result card |
| `src/cellpy_simple_gui/web/static/js/app.js` | new state (`addCells`, `staged`, `recent`, `lastResult`, `dataCollapsed`); `openAddCells`/`closeAddCells`; `stage`/`unstage`/`previewPaths`; `uploadOnly`/`onDrop`; label/reason getters; `loadFiles`/`ingestRaw` read staged; `_applyRemoteFind` → staged; `reportJobResult` → `lastResult`; `remember`/`loadRecent`; remove `showDemo`/`showLoadFiles`/`showImport`/`remoteFind.*.open` |
| `src/cellpy_simple_gui/web/static/css/app.css` | `.source-zone` (+ `.dragover`), `.staged-table`, `.segmented`, `.result-card`, `.hint.reason`, `.panel.collapsed`; remove `.disclosure`/`.import-form`/`.remote-find` once unused |
| `src/cellpy_simple_gui/core/files.py` | `Expansion.total: int = 0` (pre-cap match count) |
| `src/cellpy_simple_gui/core/models.py` | `PreviewRequest(patterns: list[str], max_files: int = 10)` |
| `src/cellpy_simple_gui/api/routers/cells.py` | `POST /files/preview` |
| `tests/test_files.py` | `total` populated on cap; unchanged for literal paths |
| `tests/test_api.py` | `/api/files/preview` (literal ok / missing / glob cap + total; served refusal via `served_client`); extend static tests: every `@click="…()"` / `x-show` identifier resolves in `app()`; exactly one `.btn-primary` per `[role=tabpanel]`; ≤ 4 `.hint` without an `x-show` guard in the sidebar + modal |
| `tests/test_gui_playwright.py` | keep both existing tests; add `test_add_cells_modal_stages_and_loads` (open modal → type a bundled `.cellpy` path → row appears → primary label `Load 1 cellpy file` → click → `.cell-card`) and `test_data_panel_collapses_after_load` |
| `README.md`, `docs/deployment.md`, `docs/llms.txt`, `docs/llms-full.txt` | labels + regenerated indexes |
| `.issueflows/04-designs-and-guides/loading-ui.md` (new), `otherpath-remote-loading.md` | decision record, UX note |

## Test strategy

Command baseline (measured on `main` @ `e056abe`, this environment):
`uv run pytest` → **301 passed, 7 skipped, 1 failed** (`test_llms_full_txt_is_current`,
pre-existing, stale `llms-full.txt`), **~24 s**. `uv run pytest -m e2e` needs
`uv sync --extra e2e && uv run playwright install chromium`; it skips cleanly
without Chromium. Static frontend checks
(`-k "app_js_parses or alpine_state"`) take ~1 s and need `node` on `PATH`.

### Test gates — when to run what

| Gate | When | Run | Must hold |
| --- | --- | --- | --- |
| **G0 baseline** | Before the first edit, on the issue branch | `uv run pytest`; `uv run pytest -m e2e` (if Chromium); screenshot sidebar default + all-expanded (server mode, `CSG_TOKEN`) | Record counts/time in `issue<N>_status.md`; the only red is the known `llms-full` drift |
| **G1 fast loop** | After **every** template / `app.js` / CSS edit, before moving on (minutes, not hours) | `uv run pytest -q -k "app_js_parses or alpine_state or preview or hint or btn_primary"` | Green. `app.js` parses; every `x-model` / `@click` identifier exists; the new static invariants hold |
| **G2 backend** | Immediately after Stage 3 backend edits, before touching the JS that calls the endpoint | `uv run pytest tests/test_files.py tests/test_api.py tests/test_uploads.py tests/test_remote_find.py tests/test_paths.py` | Green incl. new preview tests; `served_client` still refuses host paths/globs |
| **G3 stage close** | At the end of **each** stage, before its commit | `uv run pytest` (full) + manual server-mode smoke (below) for the routes that stage touched | Full suite green except the known drift (until Stage 6 fixes it); smoke checklist ticked in `issue<N>_status.md` |
| **G4 modes matrix** | End of Stage 4 and again at Stage 5 close | Manual: run once as loopback desktop-equivalent (`--server --no-open`, host paths allowed) and once served (`CSG_ALLOW_HOST_PATHS=0 uv run cellpy-simple-gui --server --no-open`, the same gate `served_client` uses in tests) | Browse/remote-find visible only when `canPick` / `hostPathsAllowed`; Upload/Drop visible when `!hostPathsAllowed`; a pasted host path in served mode is refused with the existing wording |
| **G5 e2e** | After Stage 2 (modal exists) and at Stage 5 close | `uv sync --extra dev --extra e2e && uv run playwright install chromium && uv run pytest -m e2e` | All e2e green: existing demo smoke + new modal/collapse tests; no skip caused by missing selectors |
| **G6 pre-PR / `iflow close`** | Before pushing the final commit | `uv run pytest` + `uv run pytest -m e2e` + `uv run tools/gen_llms_txt.py` (then `uv run pytest tests/test_agent_docs.py`) + capture screenshots (default sidebar, modal per tab, served mode) for the PR body | Everything green including `test_llms_full_txt_is_current`; screenshots attached; status file `- [x] Done` |
| **G7 post-merge** | After squash-merge, before `iflow cleanup` | `gh pr checks --repo cellpy/cellpy-simple-gui` (per `gh-ci` skill), then `git pull --ff-only` + `uv run pytest` on `main` | CI green; local `main` green |

Rules of thumb: never start a new stage on a red G3; never push on a red G6;
G1 is cheap enough to run after every save when iterating on the template.
Tests are not run during planning (this document); they start at G0 in
`iflow build`.

### Manual smoke checklist (G3/G4; server mode, `CSG_TOKEN=devtoken`)

1. Fresh start: default sidebar fits 1440×900 without scrolling; ≤ 4 hints.
2. `Load demo cells` → job bar → `.cell-card`s → Data panel collapses → result
   card shows `Loaded 3 cells`.
3. *Add cells → cellpy files*: paste a bundled `.cellpy` path → row `ok`;
   paste a glob matching > max → banner `Showing N of M`; remove a row;
   primary label updates; Load → cells added, modal closes, staged cleared.
4. *Add cells → Raw*: instrument unavailable → inline reason, primary disabled;
   bundled raw chip → ingest job → result.
5. *Add cells → Batch journal*: a `project.json` path still opens the project
   (classify-import routing); a `.json` journal loads.
6. Remote find (desktop-equivalent only): stub or skip the SFTP walk; verify
   the controls hide in served mode.
7. Reload → recents listed (≤ 8); Esc / backdrop / Close all close the modal.

### New tests (summary)

- Unit: `Expansion.total` on cap (`tests/test_files.py`).
- API: `/api/files/preview` literal / missing / glob-cap / served refusal.
- Static: identifiers in `@click`/`x-show` resolve; one primary per tabpanel;
  unguarded `.hint` count ≤ 4.
- e2e: modal stages + loads; Data panel collapses after load.

## Open questions

1. **Glob preview on the server** — *Recommended:* add `POST /api/files/preview`
   (reuses `expand_paths`, gives exists/total for free). Alternative: client-only
   rows for typed text and let the load job report misses (keeps the backend
   untouched but loses the "review before load" promise for globs).
2. **Demo tab in the modal?** — *Recommended:* keep *Load demo cells* as a
   one-click sidebar button only (e2e anchor, first-run path). Alternative: a
   fourth *Demo* tab.
3. **Batch journal placement** — *Recommended:* third tab in *Add cells*
   (it is a data source); `project.json` / folders stay under Project → Open.
   Alternative: leave journals in the Project panel as today.
4. **Desktop drag-and-drop paths** — *Recommended:* spike `pywebviewFullPath`
   first; if unavailable on the pinned pywebview, ship upload-fallback drops
   and note it in the design record. Alternative: no drop zone on desktop.
5. **Where `ok` toasts go** — *Recommended:* drop `ok` toasts for load/ingest
   (the result card replaces them); keep `warn`/`error`. Alternative: keep both.

## Scope check

Broad but one coherent deliverable: every stage touches the same three
frontend files plus one small endpoint, and no stage is independently useful
without the others (a modal without the staged list recreates the `;` string;
a staged list in the sidebar recreates the height problem). Splitting into
sub-issues would mostly duplicate the test gates. Per the owner's call this
stays **one issue / one PR**, with per-stage commits so review can follow the
stage order above.
