# OtherPath remote loading (#160)

## Context

A user has raw files on an SSH-only share and wants to load them in
cellpy-simple-gui. cellpy already supports `ssh://` / `sftp://` / `scp://` via
`OtherPath` (universal_pathlib / Paramiko); this app blocked that with local
`pathlib.Path.is_file()` and `expand_paths`.

## Decision

1. **Phase 1 (shipped with #160):** desktop / host-paths-allowed instances accept
   a **single** remote file URI in Load cells / Import raw. The URI is passed to
   `cellpy.get`; cellpy copies remote → local temp before open.
2. **Served mode hard-refuses** remote URIs (same gate as #120 host paths). No
   `CSG_ALLOW_REMOTE_PATHS` opt-in in this phase.
3. **Credentials:** cellpy’s `.env_cellpy` / `CELLPY_KEY_FILENAME` /
   `CELLPY_PASSWORD` only — no password form in the GUI. Config diagnostics
   already show whether those env vars are set.
4. **Phase 2 (shipped with #162):** approximate remote globbing via
   `cellpy.filefinder.find_in_raw_file_directory` (directory URI + extension +
   optional `glob_txt`), not local-style globs on SFTP URIs.
   - `cellpy_adapter.find_remote_files(directory, extensions, filter_text,
     max_files)` walks once per distinct extension with `allow_error_level=1`
     (SSH/auth failures surface as errors instead of an empty list), unions,
     de-dupes, sorts, caps at `effective_max_files`, and returns cellpy's
     already-prefixed `sftp://…` strings.
   - `POST /api/remote/find` runs it as a **job** (an SFTP walk has no progress
     hook and can take minutes; cancel is cooperative only).
   - **UX: Find populates the existing path field** (`uri1; uri2; …`) rather
     than loading immediately, so the user reviews the list and then presses
     the unchanged Load / Import button. The controls live inline in each form
     so extensions follow the selected instrument (`.cellpy`/`.h5` for Load).
   - Name filter: bare text means *contains* (`*text*`); glob characters pass
     through verbatim.
   - Local directories are refused by the finder (local globs + #120 sandbox
     already cover them); served instances get the phase-1 refusal text.
   - `filefinder.search_for_files` (run-name mode, needs prm
     `file_name_format`) is deliberately not used.

## Alternatives considered

- Teaching `expand_paths` / `glob.glob` to speak SFTP — rejected; filefinder is
  the remote-aware, project-scoped path cellpy already maintains.
- Allowing remotes in served mode — rejected for blast radius (arbitrary SSH
  from the container host).
- GUI credential editor — deferred; env + diagnostics are enough for the known
  user workflow.

## Links

- Issues: https://github.com/cellpy/cellpy-simple-gui/issues/160 (phase 1),
  https://github.com/cellpy/cellpy-simple-gui/issues/162 (phase 2, filefinder)
- cellpy remote docs: `docs/getting_started/remote_paths.md` (upstream)
- Related: #120 path sandbox, README *Remote files (SSH / SFTP)*
