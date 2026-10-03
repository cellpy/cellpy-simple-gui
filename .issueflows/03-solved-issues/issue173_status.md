# Issue #173 status

- [x] Done

## Done

- `packaging/zip_installer.py` writes `<installer>.zip` beside each `.exe`, with the installer at the archive root under its own name.
- `release.yml` and `continuous.yml` run that before `SHA256SUMS`, and the release notes name the zip.
- Docs: `docs/windows-installer.md`, `docs/releasing.md`, `README.md`, and the continuous-installer design note.

## Remaining

- None. Shipped in 0.2.1. The zip is on that tag and on later `continuous` publishes.
