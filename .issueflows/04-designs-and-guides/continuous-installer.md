# Continuous Windows installer from `main`

Issue: [#168](https://github.com/cellpy/cellpy-simple-gui/issues/168). Builds on
#117 (PyInstaller spike), #122 (Inno Setup installer), #124 (release CI).

## Context

The tag-triggered release already built the installer in CI, but between tags
the only downloadable installer was the last release — six weeks and twenty
commits behind when #168 was filed. Users wanted "the most recent version,
easily downloaded from GitHub".

## Decision

A **single rolling prerelease** under the tag `continuous`, refreshed by
`.github/workflows/continuous.yml` on every code-affecting push to `main`,
carrying one fixed-name asset `cellpy-simple-gui-continuous-setup.exe`,
the same installer as `cellpy-simple-gui-continuous-setup.zip` (#173), plus
`SHA256SUMS`. The build itself was extracted from `release.yml` into a reusable
`workflow_call` workflow (`windows-installer.yml`) so the tagged and the rolling
installer share one recipe, including the #117 smoke-test gate.

Supporting choices:

- **Edit, never recreate.** Creating a release notifies release-watchers;
  editing one (`gh release upload --clobber`, `gh release edit`) does not. The
  tag is force-moved (`git push --force origin refs/tags/continuous`) — the one
  legitimate force-push in the repo, because the tag is a pointer, not history.
- **`--prerelease --latest=false`** so `/releases/latest` keeps pointing at the
  real release.
- **Tag name must not match `v*`.** `release.yml`, `publish.yml` and
  `container.yml` all trigger on that glob; a match would publish every merge to
  PyPI and GHCR. `tests/test_packaging.py` parses the four workflows and asserts
  the rolling tag matches none of their tag globs.
- **Display vs resource version.** Inno's `VersionInfoVersion` must be numeric,
  so `installer.iss` takes `AppVersion` (numeric) and an optional `BuildId`
  (`main.abc1234`) that only reaches the display version (`0.1.1+main.abc1234`).
  A tag build passes no `BuildId` and is unchanged. Same `AppId`, so either
  installer upgrades the other in place.
- **Build on PR, publish on push** (the `container.yml` shape): a PR touching
  `packaging/**` or the two workflows runs the Windows build + smoke test and
  stops; only `main` publishes. Path filters skip docs-only merges;
  `concurrency` with `cancel-in-progress` collapses rapid merges to the newest.

## Alternatives considered

- **Workflow artifacts** — need a GitHub login, expire after 90 days, arrive
  zipped. Not "easily downloaded".
- **Nightly cron** — predictable cost but lags up to a day and rebuilds when
  nothing changed; per-push with path filters is both fresher and cheaper.
- **Recreate the release each time** — simpler script, but spams watchers.
- **Sha in the asset name** — unique per build, but the download URL would move
  on every merge; the release notes and the display version carry the sha instead.
- **macOS / Linux bundles** — still out of scope per the deployment epic: an
  unsigned macOS `.app` is refused by Gatekeeper outright (notarisation needs a
  paid developer account) and pywebview on Linux needs GTK/WebKit or Qt system
  packages a bundle cannot carry cleanly. `uv tool install
  "cellpy-simple-gui[desktop]"` remains the cross-platform route.
- **Wheel on the continuous release** — rejected: a wheel versioned `0.1.1` that
  is not `0.1.1` is a trap; `uv tool install git+https://…` serves that need.
