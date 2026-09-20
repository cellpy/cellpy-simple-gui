# Issue #162 — Plan: remote file find via `cellpy.filefinder` (OtherPath phase 2)

## Goal

Let a desktop user point **Load cells** / **Import raw** at a remote
**directory** URI (`sftp://user@host/path/`), optionally narrow by a name
filter, and get back concrete `sftp://…/file.ext` URIs that the existing
load / ingest jobs already accept (phase 1, #160) — without teaching
`expand_paths` to glob over SFTP.

## Constraints

- **cellpy boundary:** `cellpy.filefinder` / `OtherPath` are imported only in
  `core/cellpy_adapter.py` (lazy, inside the function, like `_get`). Routers and
  UI deal in strings.
- **Policy:** same gate as phase 1 — `paths.remote_paths_allowed()`; a served
  instance refuses with the same wording as `expand_paths` (“SSH/SFTP remotes
  are desktop-only”). No `CSG_ALLOW_REMOTE_PATHS` opt-in.
- **Remote directories only.** A local directory is *not* routed through
  filefinder (local globs + #120 sandbox already cover that); a non-remote
  input is an error pointing the user at globs.
- **`max_files` ceiling** from `files.effective_max_files` applies to the find
  result, so “Find” can never return more than “Load” would accept.
- **Long walks:** SFTP `rglob` over a shared `rawdatadir` can take minutes and
  gives no progress callback → run as a job (cancel is cooperative; the walk
  itself cannot be interrupted, so the message says so).
- **Out of scope** (issue text): SFTP folder browser UI, served-mode SSH
  allow-list, GUI credential editor. Also: setting cellpy `rawdatadir` from the
  GUI, `search_for_files` run-name mode (needs prm `file_name_format`; the
  `glob_txt` filter already covers “contains run id”).
- Design doc to follow / update:
  [`otherpath-remote-loading.md`](../04-designs-and-guides/otherpath-remote-loading.md);
  brief in [`this-project.md`](../04-designs-and-guides/this-project.md).

### Prior art

- `cellpy.filefinder.find_in_raw_file_directory(raw_file_dir, project_dir,
  extension, glob_txt, allow_error_level)` — verified installed signature. Wraps
  `OtherPath.rglob(glob, files_only=True)`; for external paths returns
  `match.full_path`, which **already carries the `sftp://user@host` prefix**
  (checked: `OtherPath('sftp://u@h/x/a.res').full_path` round-trips). Logs a
  warning at ≥ `_LARGE_FILE_LIST_WARN` files; `allow_error_level=1` raises
  `SearchError` instead of swallowing SSH failures — we want that.
- `cellpy.filefinder.search_for_files(run_name, …)` — run-name centric, depends
  on prm `file_name_format`; **not used** (coexist, mention in doc).
- [`core/paths.py`](../../src/cellpy_simple_gui/core/paths.py):
  `is_remote_uri`, `remote_paths_allowed`, `PathNotAllowed` — reuse as the gate.
- [`core/files.py`](../../src/cellpy_simple_gui/core/files.py):
  `expand_paths` remote branch (single URI passthrough, refuses remote globs,
  desktop-only error text) and `effective_max_files` — reuse text + cap; the
  found URIs flow through this branch unchanged.
- [`core/cellpy_adapter.py`](../../src/cellpy_simple_gui/core/cellpy_adapter.py):
  `_filename_for_get` / `_get` indirection pattern — mirror with a
  `_find_in_raw_file_directory` seam so tests monkeypatch the adapter, not cellpy.
  `list_instruments()` already exposes `suffixes` per instrument (e.g.
  `['.res']`, `['.nda*']`) → the UI knows which extensions to search.
- [`api/routers/ingest.py`](../../src/cellpy_simple_gui/api/routers/ingest.py) /
  [`cells.py`](../../src/cellpy_simple_gui/api/routers/cells.py): job pattern
  (`get_job_manager().submit(kind, fn, …)` → `{"job_id"}`) and result shape
  `{added, errors, notes}` — mirror for the find job with `{paths, total,
  errors, notes}`.
- [`web/static/js/app.js`](../../src/cellpy_simple_gui/web/static/js/app.js):
  `runJob` + `streamJob` + `reportJobResult` (keys on `"added" in r`) — extend
  `reportJobResult` for a `"paths"` result; `loadFiles` / `ingestRaw` split the
  text field on `;`, so populating the field with `uris.join("; ")` needs no
  new load code.
- `tests/test_ingest.py` (`FakeRemote` + `_get` monkeypatch), `tests/test_paths.py`
  (`local` / `served` fixtures), `tests/test_api.py` (`TestClient(create_app())`
  + job polling) — test conventions to follow.
- `tools/gen_api_reference.py` SECTIONS + `tests/test_api_reference.py` —
  if the adapter adopts a new cellpy call, add it to the reference list and
  regenerate (`uv run tools/gen_api_reference.py`), otherwise the guides drift.
- Toolbox `.issueflows/00-tools/`: empty (README only). Graph: community 83
  (`expand_paths`) + 104 (`cellpy_adapter.py`) confirm the surface is
  files/paths → adapter → jobs → app.js; plots/library untouched.

## Approach

Data flow: UI (dir URI + filter + extensions from instrument) → `POST
/api/remote/find` → job → `cellpy_adapter.find_remote_files(...)` →
filefinder → prefixed URI list (capped) → job result → UI writes
`uri1; uri2; …` into the existing path field → user clicks **Load files** /
**Import & process** → unchanged phase-1 path.

1. **Adapter** — `find_remote_files(directory: str, *, extensions:
   Sequence[str] = (), glob_txt: str | None = None, max_files: int) ->
   RemoteFind` (small dataclass `paths`, `total`, `notes`, `errors`).
   - Normalise: strip quotes/whitespace; require `is_remote_uri(directory)`
     else `ValueError("Remote find needs an sftp:// … directory; for local
     folders use a glob")`. Gate `remote_paths_allowed()` → `PathNotAllowed`
     with the phase-1 wording.
   - `glob_txt`: `None`/blank → `"*"`; a bare word without glob chars becomes
     `*word*` (“contains”), a pattern with `*`/`?` is passed as-is.
   - Extensions: empty → one call with `extension=None`; else one call per
     suffix, `extension=suffix.lstrip(".")` (a `.nda*` style suffix survives
     because filefinder only concatenates). `allow_error_level=1` so SSH /
     auth failures raise and land in `errors` via `explain_load_error`-style
     text, not a silent empty list.
   - Union, de-dupe, stable sort; `total = len(all)`; cap to `max_files` with
     the note `Found N files; keeping the first M (raise “max” or narrow the
     folder / filter)`. Also append cellpy’s own advice when `total` is large
     (≥ the same threshold filefinder warns at): prefer a project-scoped dir.
   - Seam `_find_in_raw_file_directory(**kwargs)` that does the lazy `from
     cellpy import filefinder` — the only thing tests monkeypatch.
2. **Model** — `RemoteFindRequest(directory: str, extensions: list[str] = [],
   filter: str | None = None, max_files: int = 10)` in `core/models.py`.
3. **Router** — new `api/routers/remote.py` with `POST /remote/find` →
   `get_job_manager().submit("remote-find", _remote_find_job, req)`; job
   calls `effective_max_files(req.max_files)` then the adapter; progress
   message `Searching <dir> … (SFTP walks can take a while)`. Result:
   `{"paths": [...], "total": N, "errors": [...], "notes": [...]}`.
   `PathNotAllowed` / `ValueError` → returned in `errors` (job status stays
   `done`, consistent with how `expand_paths` refusals are reported); other
   exceptions bubble → job `error`. Register in `api/app.py` behind the same
   token guard.
4. **UI** — in both **Add cellpy files** and **Import raw** forms, only when
   `hostPathsAllowed`: a compact “Find on remote…” disclosure with
   *Remote folder* (`sftp://user@host/path/`), *Name filter* (optional),
   **Find** button. Extensions: Load → `[".cellpy", ".h5"]`; Import → the
   selected instrument’s `suffixes` (fallback: none = all files). On a
   `paths` result: write `paths.join("; ")` into `filesPath` / `ingest.paths`,
   notify `Found N (showing M)` + notes/errors; the user reviews and presses
   the existing Load / Import button. State: `remoteFind: {dir, filter}` for
   each panel. `reportJobResult` gets a `"paths" in r` branch.
   `job.kind === "remote-find"` shares the one job bar (no second bar).
5. **Docs** — README *Remote files (SSH / SFTP)*: replace the “planned as a
   follow-up” sentence with a short *Find files on a remote folder* paragraph
   (dir URI, filter, extensions come from the instrument, `max` cap, prefer
   project-scoped folders). `docs/deployment.md` already says desktop-only —
   verify wording still holds. Update the design doc’s Decision §4 to
   “shipped (#162)”, record the populate-the-field UX and the no-`search_for_files`
   choice.
6. **API reference** — add `filefinder.find_in_raw_file_directory` to
   `tools/gen_api_reference.py` SECTIONS (Files / discovery), regenerate
   `docs/api-reference.md` and the byte-identical skill copy that
   `test_the_reference_and_the_skill_copy_are_byte_identical` checks.

Ordering: adapter + tests → model/router + API test → app.js/index.html →
docs + design doc + api-reference → `uv run pytest`.

## Files to touch

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | `RemoteFind` dataclass, `find_remote_files(...)`, `_find_in_raw_file_directory` seam |
| `src/cellpy_simple_gui/core/models.py` | `RemoteFindRequest` |
| `src/cellpy_simple_gui/api/routers/remote.py` (new) | `POST /remote/find` job endpoint |
| `src/cellpy_simple_gui/api/app.py` | register `remote.router` |
| `src/cellpy_simple_gui/web/templates/index.html` | “Find on remote…” controls in both forms (desktop only) |
| `src/cellpy_simple_gui/web/static/js/app.js` | `remoteFind` state, `findRemote(panel)`, `reportJobResult` `paths` branch |
| `tests/test_ingest.py` | adapter unit tests (prefix passthrough, multi-ext union/dedupe, filter → `*word*`, cap + note, served refusal, non-remote dir refusal, SearchError → errors) |
| `tests/test_api.py` | `POST /api/remote/find` job round-trip with monkeypatched adapter; 400 on empty directory |
| `README.md`, `docs/deployment.md` | user docs |
| `.issueflows/04-designs-and-guides/otherpath-remote-loading.md` | phase 2 decision record |
| `tools/gen_api_reference.py`, `docs/api-reference.md`, skill copy | add filefinder call, regenerate |

## Test strategy

- Command: `uv run pytest` (from repo root). No live SFTP; everything through
  the `_find_in_raw_file_directory` seam and the `local` / `served` fixtures.
- Adapter: returns cellpy’s prefixed strings untouched; per-extension calls
  with `extension` sans dot and `glob_txt`; union + de-dupe + sort; `total` vs
  capped `paths` + note text; `served` → `PathNotAllowed`; local dir →
  `ValueError`; `SearchError` → surfaced in `errors`.
- API: job submits, polls to `done`, result has `paths`/`total`; served mode
  returns the refusal in `errors`; missing `directory` → 400.
- Regression: existing phase-1 tests (`test_paths.py` remote block,
  `test_ingest.py` remote block, `test_packaging.py::test_remote_paths_are_never_touched`)
  must stay green; `test_api_reference.py` after regeneration.
- Manual (server mode, `--server --no-open`, `CSG_TOKEN`): the find controls
  render on loopback and are hidden when host paths are refused; the job bar,
  notification and field population are exercised through the API with a
  stubbed adapter. No live SSH host is available, so the real SFTP walk is not
  part of the manual pass (cellpy covers that upstream).

## Open questions

1. **Result handling UX** — *Recommended:* **Find populates the path field**
   (user reviews, then presses the existing Load / Import). Alternative: a
   one-shot “Find & load” that submits the load job immediately.
2. **Where the find controls live** — *Recommended:* inline disclosure inside
   each existing form (Load cells and Import raw), so extensions can follow the
   selected instrument. Alternative: one shared “Remote find” block with a
   target dropdown.
3. **Filter semantics** — *Recommended:* bare text = “contains” (`*text*`),
   patterns with `*`/`?` passed verbatim. Alternative: always verbatim glob.
4. **API reference update** — *Recommended:* include
   `filefinder.find_in_raw_file_directory` (small, keeps the guides honest).
   Alternative: skip and leave the reference as is.

## Scope check

One coherent PR: adapter function + one endpoint + two small form additions +
docs. No refactors mixed in; no split/epic needed. Folder browser and
served-mode allow-list stay deferred as the issue states.
