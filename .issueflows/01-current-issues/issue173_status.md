# Issue #173 status

- [ ] Done

## Done

- `packaging/zip_installer.py` writes `<installer>.zip` beside each `.exe`, with the installer at the archive root under its own name.
- `release.yml` and `continuous.yml` run that before `SHA256SUMS`, and the release notes name the zip.
- Docs: `docs/windows-installer.md`, `docs/releasing.md`, `README.md`, and the continuous-installer design note.

## Remaining

- Land the branch and close the GitHub issue. The zip appears on the next tag and the next `continuous` publish, not on releases that already exist.
