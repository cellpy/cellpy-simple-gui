# Issue #160 — Plan: OtherPath remote loading

## Goal

Let a desktop user load raw / cellpy files that live on an SSH-only remote host
by typing `ssh://` / `sftp://` / `scp://` URIs (cellpy’s `OtherPath`), without
breaking the existing local-path + sandbox behaviour (#120).

This issue’s GitHub text asks to **create a plan**; the first deliverable is a
durable design doc plus a minimal, shippable MVP if the open questions below
resolve that way. Broader browse/credential UX can follow in separate issues.

## Constraints

- **cellpy boundary:** only `core/cellpy_adapter.py` (and optionally a tiny
  helper next to it) may import cellpy / `OtherPath`. Routers and UI stay
  path-string oriented.
- **Do not weaken #120 sandbox** for served instances: remote URIs that open
  SSH to arbitrary hosts are a host-blast-radius concern. Default: remote load
  **desktop / host-paths-allowed only**; refuse in served mode with a clear
  message (or require an explicit future allow-list — open question).
- **Credentials stay out of the UI and out of project `cellpy.toml`.** cellpy
  already uses `CELLPY_KEY_FILENAME` / `CELLPY_PASSWORD` / `.env_cellpy`; the
  config diagnostics panel already reports whether those env vars are set
  (`core/cellpy_config.py`). Prefer documenting + surfacing that over inventing
  a password form.
- **`OtherPath` is not a `pathlib.Path` subclass.** Adapter code that does
  `Path(path).is_file()` will reject every remote URI today.
- **cellpy copies remote → local temp before instrument / HDF5 open.** Load
  latency and temp-disk use are expected; do not try to stream HDF5 over SFTP
  in the app.
- **Known upstream limits:** OpenSSH `Host` aliases in URIs often fail DNS
  (cellpy #687); use real hostname + `CELLPY_KEY_FILENAME`. Remote save is
  unsupported upstream — out of scope.
- **Scope discipline:** one PR should not also redesign browse dialogs, batch
  discovery against a whole `rawdatadir`, or multi-tenant SSH policy.

### Prior art

- `cellpy.internals.otherpath.OtherPath` / docs
  `docs/getting_started/remote_paths.md` (cellpy ≥2.1.3) — schemes, credentials,
  `copy()`, truthful `exists`/`is_file`.
- [`core/paths.py`](../../src/cellpy_simple_gui/core/paths.py) — local vs served
  sandbox (#120); UNC/drive checks; `://` remote URIs are not handled today.
- [`core/files.py`](../../src/cellpy_simple_gui/core/files.py) `expand_paths` —
  local glob + `resolve_input`; entry point for both `/load/files` and `/ingest`.
- [`core/cellpy_adapter.py`](../../src/cellpy_simple_gui/core/cellpy_adapter.py)
  `load_file` / `load_raw` — force `pathlib.Path` + local `is_file()` before
  `cellpy.get`.
- [`core/cellpy_config.py`](../../src/cellpy_simple_gui/core/cellpy_config.py) —
  `_SECRET_ENV_VARS` already lists `CELLPY_*` credential env presence.
- [`__main__.py`](../../src/cellpy_simple_gui/__main__.py) `_anchor_cellpy_paths`
  — already leaves `rawdatadir` alone when it contains `://`.
- **`cellpy.filefinder`** (`find_in_raw_file_directory`, `list_raw_file_directory`,
  `search_for_files`) — remote-aware discovery via `OtherPath.rglob(...,
  files_only=True)` / optional remote `find -L`; takes `raw_file_dir`,
  `project_dir`, `extension`, `glob_txt` / `run_name`. Prefer this over teaching
  app `expand_paths` to speak SFTP.
- Browser upload path ([`docs/deployment.md`](../../docs/deployment.md)) —
  alternative for served mode (bring files to the instance); not a substitute
  for SSH-only lab shares on the user’s desktop.
- Toolbox: none relevant (`00-tools/` empty).
- Graph: `expand_paths` community + load/ingest job community — confirms the
  change surface is files → adapter → jobs, not plot/library.

## Approach

### Phase 1 — MVP (this issue after Accept)

Single-file remote URI only (no remote glob in `expand_paths`).

1. **Detect remote URI** in `core/files.py` (scheme in
   `ssh://` / `sftp://` / `scp://`). Do not run local `glob` / `Path.resolve`
   on them.
2. **Policy gate:** if `sandbox_root()` is set (served), append a clear error
   and skip; if host paths allowed (desktop / loopback), keep the URI string.
3. **Existence check via OtherPath** inside the adapter (keep OtherPath import
   only in the adapter; pass strings upward). Refuse missing remotes with the
   same “Not found” style errors as local.
4. **Adapter:** `load_file` / `load_raw` accept a path string; if remote, pass
   it through to `cellpy.get(filename=...)` **without** `Path(...).is_file()`.
   Local paths keep today’s check.
5. **UI (minimal):** path placeholders / help text mention
   `sftp://user@host/path/file.res`; optional one-line note when config
   diagnostics show `CELLPY_KEY_FILENAME` unset. No new credential form.
6. **Docs:** short “Remote files (SSH)” subsection in README or
   `docs/deployment.md` (desktop-focused) pointing at cellpy’s credential env
   vars and the Host-alias workaround.
7. **Durable design note** under
   `.issueflows/04-designs-and-guides/otherpath-remote-loading.md` recording
   decisions (desktop-only MVP, env credentials, filefinder as phase 2, no
   remote save).

### Phase 2 — filefinder “approx glob” (follow-up issue; decided)

Not free-form `sftp://…/**/*.res` through local `glob`. Instead a small remote
find UX that wraps cellpy’s filefinder behind `cellpy_adapter`:

- Inputs: remote **directory** URI (or config `rawdatadir`) + optional
  `project_dir` / name filter (`glob_txt` or `run_name`) + **extension** from
  the Import instrument (or `.cellpy` for Load cells).
- Call `filefinder.find_in_raw_file_directory(...)` (or `search_for_files` when
  the user has a run id); return `sftp://…` URI strings with `with_prefix`.
- Enforce existing `max_files`; if the dump is huge, surface a clear “narrow
  the folder / filter” note (cellpy already warns that dumping a shared
  `rawdatadir` over SFTP is expensive — prefer project-scoped dirs).
- Feed matches into the same load/ingest jobs as pasted URIs from phase 1.
- Same desktop-only policy gate as phase 1.

Phase 2 is a separate issue/PR so phase 1 stays shippable without browse UI.

### Explicitly deferred (later than phase 2)

- Full folder-browser UI (tree / picker over SFTP).
- Setting / editing cellpy `Paths.rawdatadir` to a remote URI from the GUI.
- Connection self-test button (`cellpy.internals.connections.check_connection`).
- Served-mode allow-list of hosts or “SSH jump from container” packaging.
- Paramiko/SSH agent UX polish beyond documenting env vars.

### Ordering

**This PR:** adapter + `expand_paths` policy → tests → tiny UI/help → design doc
+ README → stop.

**Next issue:** adapter `find_remote_files(...)` via filefinder → API/job →
minimal UI (dir + filter + extension) → tests with mocked filefinder.

## Files to touch

### Phase 1 (this PR)

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | Remote-aware `load_file` / `load_raw` (skip local `Path.is_file`; pass URI to `cellpy.get`) |
| `src/cellpy_simple_gui/core/files.py` | Detect remote URIs; skip local expand; desktop-only gate via `paths` |
| `src/cellpy_simple_gui/core/paths.py` | Small helper e.g. `is_remote_uri` / `assert_remote_allowed` (or keep URI helpers in `files.py` if thinner) |
| `src/cellpy_simple_gui/web/templates/index.html` (+ maybe `app.js`) | Placeholder / hint for sftp URIs |
| `tests/test_files.py`, `tests/test_paths.py`, adapter/unit tests | Mock OtherPath / monkeypatch `cellpy.get`; served refuses remotes; desktop URI passthrough |
| `docs/` or `README.md` | User-facing remote-load note |
| `.issueflows/04-designs-and-guides/otherpath-remote-loading.md` | Decision record (incl. phase 2 filefinder) |

### Phase 2 (follow-up issue)

| Path | Change |
| --- | --- |
| `src/cellpy_simple_gui/core/cellpy_adapter.py` | `find_remote_files(...)` wrapping `cellpy.filefinder` |
| API router + models | Endpoint or job to list remote matches (dir + filter + extension) |
| UI | Minimal “Find on remote” controls; feed URIs into existing load/ingest |
| Tests | Monkeypatch filefinder; assert caps / policy / URI prefix |

## Test strategy

- Command: `uv run pytest`
- Phase 1 unit tests (no live SFTP in CI):
  - `is_remote_uri` / expand_paths leaves `sftp://…` intact under host-paths-allowed
  - expand_paths errors clearly under served sandbox
  - adapter `load_file`/`load_raw` call `cellpy.get` with the URI string when remote (monkeypatch)
  - local paths unchanged (existing `tests/test_files.py` / `tests/test_paths.py` still pass)
- Phase 2 (later): mocked filefinder returns prefixed URIs; `max_files` truncation notes;
  served mode still refuses.
- Do **not** require Docker SFTP property tests in this app’s CI (that lives upstream in cellpy).

## Open questions

1. **Deliverable for this PR:** Phase 1 MVP code + design doc (recommended), or
   **design doc / epic split only** with implementation filed as follow-ups?
2. **Served mode:** hard-refuse remote URIs (recommended), or allow with an
   explicit env opt-in (e.g. `CSG_ALLOW_REMOTE_PATHS=1`)?
3. **Remote “glob”:** **Decided** — Phase 1 = single-file URI only; Phase 2 =
   filefinder-based find (dir + extension + optional `glob_txt` / run name),
   not local-style globs on remote URIs. File as a follow-up issue after phase 1.
4. **Credential UX:** document + existing diagnostics only (recommended), or add
   a Settings affordance to set `CELLPY_KEY_FILENAME` for the process?

## Scope check

Full remote folder browser is still later than phase 2. Phase 1 is one coherent
PR; phase 2 is one follow-up issue. If Q1 is “plan only”, convert this file into
the design doc and open both implementation issues instead of coding in
`/iflow-build`.
