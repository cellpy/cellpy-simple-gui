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
4. **Phase 2 (follow-up):** approximate remote globbing via
   `cellpy.filefinder.find_in_raw_file_directory` (directory URI + extension +
   optional `glob_txt` / run name), not local-style globs on SFTP URIs.

## Alternatives considered

- Teaching `expand_paths` / `glob.glob` to speak SFTP — rejected; filefinder is
  the remote-aware, project-scoped path cellpy already maintains.
- Allowing remotes in served mode — rejected for blast radius (arbitrary SSH
  from the container host).
- GUI credential editor — deferred; env + diagnostics are enough for the known
  user workflow.

## Links

- Issue: https://github.com/cellpy/cellpy-simple-gui/issues/160
- cellpy remote docs: `docs/getting_started/remote_paths.md` (upstream)
- Related: #120 path sandbox, README *Remote files (SSH / SFTP)*
