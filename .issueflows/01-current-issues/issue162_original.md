# Issue #162: Remote file find via cellpy.filefinder (OtherPath phase 2)

Source: https://github.com/cellpy/cellpy-simple-gui/issues/162

## Original issue text

Follow-up to #160 phase 1 (single-file `sftp://` / `ssh://` / `scp://` URI load on desktop).

## Goal

Approximate remote “globbing” without teaching app `expand_paths` to speak SFTP: wrap `cellpy.filefinder.find_in_raw_file_directory` (and optionally `search_for_files`) behind `cellpy_adapter`.

## Spec

- Inputs: remote **directory** URI (or config `rawdatadir`) + optional project/name filter (`glob_txt` / run name) + **extension** from Import instrument (or `.cellpy` for Load).
- Return prefixed `sftp://…` URI strings; feed into existing load/ingest jobs.
- Enforce `max_files`; warn if the dump is huge (prefer project-scoped dirs).
- Same desktop-only policy as #160 (refuse when served).

## Out of scope

Full SFTP folder browser UI; served-mode SSH allow-list; GUI credential editor.

See `.issueflows/04-designs-and-guides/otherpath-remote-loading.md` and the #160 plan.
