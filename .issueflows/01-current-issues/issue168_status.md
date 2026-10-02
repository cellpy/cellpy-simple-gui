# Status — Issue #168: Create installer using CI

- [ ] Done

PR: https://github.com/cellpy/cellpy-simple-gui/pull/170 (#170, draft)

## 2026-10-02 — picked, captured, planned

- Picked via `iflow pick 168`; branch `cursor/168-ci-installer-2654` off `origin/main` (even, clean).
- Captured `issue168_original.md` (no comments on the issue).
- Gap analysis: the tag-triggered CI installer already exists (#124, `release.yml`);
  what is missing is a downloadable build of the **newest `main`**, plus a stale
  paragraph in `docs/releasing.md`. Multi-OS installers were ruled out by the
  deployment epic — surfaced as an open question rather than silently dropped.
- Plan accepted with all four defaults (per-push cadence, tag `continuous`,
  Windows-only, no wheel on the rolling release).

## 2026-10-02 — built

### What's done

- `.github/workflows/windows-installer.yml` — **new** reusable `workflow_call`
  build (checkout → uv → PyInstaller → `smoke_test.py` → ISCC → artifact),
  extracted from `release.yml`; inputs `ref`, `channel`, `output-base-name`,
  `artifact-name`; outputs `version`, `build-id`.
- `.github/workflows/continuous.yml` — **new**: push-to-`main` (path-filtered),
  PR (build-only) and dispatch; `publish` job moves tag `continuous`, uploads
  `cellpy-simple-gui-continuous-setup.exe` + `SHA256SUMS` with `--clobber`,
  edits (never recreates) the prerelease with `--latest=false`.
- `.github/workflows/release.yml` — `windows-installer` job now `uses:` the
  reusable workflow; everything else untouched.
- `packaging/installer.iss` — optional `BuildId` / `OutputBaseName` defines;
  `AppVersion`/`AppVerName` show `DisplayVersion`, `VersionInfoVersion` stays
  numeric; tag builds unchanged.
- `packaging/build_installer.ps1` — `-BuildId` pass-through; also fixed its
  version lookup, which still read `version = …` from `pyproject.toml` (gone
  since the version became dynamic) and so always threw.
- `tests/test_packaging.py` — five new essential guards: numeric version
  resource, rolling tag never matches a `v*` trigger, build-on-PR /
  publish-only-from-main, both callers share the one reusable build.
  `pyyaml` declared in the `dev` extra (was only transitive via cellpy).
- Docs: `docs/releasing.md` (stale "#124" paragraph replaced; new rolling
  release section), `docs/windows-installer.md` (*Downloading*), `README.md`
  (download links), `packaging/README.md` (#168 section),
  `.issueflows/04-designs-and-guides/continuous-installer.md` (decision note);
  `llms-full.txt` regenerated with `tools/gen_llms_txt.py`.
- `uv run pytest`: 313 passed, 7 skipped.

### Remaining work

- Watch the PR's **Continuous build / build** check — the new `pull_request`
  trigger runs the real Windows freeze + smoke test + ISCC on the PR (first
  rehearsal of `main`'s frozen build since the 2026-08-16 failure). `publish`
  is gated off on PRs.
- First `continuous` release appears on merge to `main`.
- `/iflow-close` (HISTORY step skipped automatically: no `HISTORY.md` in the repo).
