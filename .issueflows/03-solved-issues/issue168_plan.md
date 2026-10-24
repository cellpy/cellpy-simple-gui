# Plan — Issue #168: Create installer using CI

Source: https://github.com/cellpy/cellpy-simple-gui/issues/168

## Goal

Make the **newest code on `main`** downloadable from GitHub as a ready-made
Windows installer, built and smoke-tested by CI on every code-affecting merge —
without waiting for a version tag. Keep the existing tag-triggered release flow
exactly as it is.

## Where we actually are (gap analysis)

Half of #168 already exists and the issue text does not reflect it:

| Ask in #168 | State on `main` today |
|---|---|
| "installer … made by CI" | **Done** in #124: `release.yml` builds the Windows installer on a `v*` tag (`windows-latest`, PyInstaller → `smoke_test.py` → Inno Setup → GitHub Release). `v0.1.1` (2026-08-16) carries `cellpy-simple-gui-0.1.1-setup.exe`. |
| "most recent version can be easily downloaded from github" | **Not done.** `main` is 20 commits past `v0.1.1`; the only downloadable installer is six weeks old. Workflow artifacts are not an answer: they need a GitHub login, expire (90 days), and come zipped. |
| "installers … for several OS" | **Decided out of scope** in the deployment epic (`05-epics/next-phase-deployment-and-docs.md`: "Windows, plus an installer-free uv/pipx route — no macOS signing, no Linux packaging, for now"). See *Open questions*. |
| — | `docs/releasing.md` still says the installer "is not built on the runner … Automating that is #124" — stale since #124 landed. |
| — | The last `release.yml` rehearsal from `main` (2026-08-16 18:43) **failed** in `smoke_test.py` on the Arbin `.res` check: #143 had just reworded the ODBC error. The `_MISSING_ODBC` list now covers both vocabularies and `test_packaging.py` pins it, so `main` should pass — but nobody has run it since. The continuous build is also the thing that will keep that from silently rotting again. |

So the real deliverable is a **rolling "latest from main" prerelease** carrying
the Windows installer, plus the doc corrections.

## Constraints

- **No change to the tag release path.** `publish.yml` / `container.yml` /
  `release.yml` all trigger on `tags: ["v*"]`; the rolling tag must **not**
  match `v*`, or a continuous build would publish to PyPI/GHCR. Tests pin this.
- **No release spam.** Creating a new GitHub Release notifies everyone watching
  releases. The rolling release is created **once** and thereafter only
  *edited* (`gh release upload --clobber`, `gh release edit`), which does not
  notify. The tag is moved, not recreated.
- **A build that is not smoke-tested is not a build** (#117 rule). The
  continuous job runs the same 15-check `packaging/smoke_test.py` as the
  release; a red smoke test publishes nothing and leaves the previous
  continuous installer in place.
- **Inno Setup `VersionInfoVersion` must stay numeric** (`a.b.c[.d]`). The
  installer's *display* version may carry a build suffix; the Win32 version
  resource may not. Today `installer.iss` uses one `AppVersion` define for both,
  so a `0.1.1+main.193c553` would fail `ISCC`.
- **Single source of version** stays `src/cellpy_simple_gui/__init__.py`
  (`[tool.hatch.version]`); the continuous build *appends* to it, never edits it.
- Windows runner minutes are free for a public repo, but ~12 min per build is
  still worth gating: path filters so docs-only merges do not rebuild, and a
  `concurrency` group so rapid merges only build the newest commit.
- `uv run pytest` must stay green; `tests/test_packaging.py` is `essential`.
- Branch note: created in-place as `cursor/168-ci-installer-2654` (cloud-agent
  naming constraint; worktree-first was not available in this environment).

### Prior art

- `.github/workflows/release.yml` — `windows-installer` job (checkout → setup-uv
  → `uv sync --extra build --extra desktop --extra export` → PyInstaller →
  smoke test → `ISCC` with version read from `__init__.py` → artifact).
  **Reuse by extraction**, not copy: becomes a `workflow_call` reusable workflow
  consumed by both the tag release and the continuous build.
- `.github/workflows/container.yml` — the pattern of *build on PR, publish on
  push* so a recipe is exercised when changed rather than at release time.
  **Mirror** for the new workflow (PR touching it builds; only `main` publishes).
- `.github/workflows/essential-tests.yml` — path-based "code changed?" gate.
  Mirror the path list for the continuous trigger.
- `packaging/installer.iss` — `AppVersion` define, `OutputBaseFilename`,
  `VersionInfoVersion`. **Extend** with optional defines (below).
- `packaging/build_installer.ps1` — local build; pass-through of the new
  optional define so a dev can reproduce a continuous build (**coexist**, small).
- `packaging/smoke_test.py` — unchanged, reused as the gate.
- `tests/test_packaging.py` — text-level assertions on `installer.iss` and the
  spec; **extend** with workflow/iss guards.
- `docs/releasing.md`, `docs/windows-installer.md`, `README.md` — download and
  release docs; **update** (one stale paragraph, one new section each).
- Toolbox `.issueflows/00-tools/`: empty — nothing to reuse.
- Graph: `GRAPH_REPORT.md` community 75 is `test_packaging.py`; no other
  packaging/CI community — grep-only was sufficient.

## Approach

### 1. Extract the installer build into a reusable workflow

New `.github/workflows/windows-installer.yml`, `on: workflow_call` with inputs:

- `ref` (string, default `github.sha` of the caller)
- `build-id` (string, optional) — e.g. `main.193c553`; empty for tag releases
- `artifact-name` (string, default `windows-installer`)

Body = today's `windows-installer` job, with the `ISCC` step passing
`/DBuildId=<build-id>` and `/DOutputBaseName=<name>` when `build-id` is set.
Uploads `dist/installer/*.exe` as the named artifact (`if-no-files-found: error`).

`release.yml`'s `windows-installer` job becomes
`uses: ./.github/workflows/windows-installer.yml` with `ref: ${{ inputs.ref || github.ref }}`.
Everything else in `release.yml` (python-dists, release notes, tag-only gating)
is untouched. The job id and `needs:` stay the same so no check names move.

### 2. Teach `installer.iss` about a build suffix without breaking the version resource

```ini
; Overridable: ISCC /DAppVersion=1.2.3 [/DBuildId=main.abc1234] [/DOutputBaseName=...]
#ifdef BuildId
  #define DisplayVersion AppVersion + "+" + BuildId
#else
  #define DisplayVersion AppVersion
#endif
#ifndef OutputBaseName
  #define OutputBaseName "cellpy-simple-gui-" + DisplayVersion + "-setup"
#endif

AppVersion={#DisplayVersion}            ; free text — shows in Add/Remove Programs
AppVerName={#AppName} {#DisplayVersion}
VersionInfoVersion={#AppVersion}        ; numeric only — Win32 version resource
OutputBaseFilename={#OutputBaseName}
```

Tag builds are byte-for-byte the same as today (no `BuildId` → identical
defines). `AppId` is unchanged, so installing a continuous build over a stable
one (or vice versa) *replaces* it, like any upgrade — documented.

`build_installer.ps1` gets an optional `-BuildId` parameter that forwards the
define (two lines), so the CI artifact is reproducible locally.

### 3. New `continuous.yml` — the rolling prerelease

```yaml
name: Continuous build
on:
  push:
    branches: [main]
    paths: [src/**, packaging/**, pyproject.toml, uv.lock, .python-version,
            .github/workflows/continuous.yml, .github/workflows/windows-installer.yml]
  pull_request:
    paths: [packaging/**, .github/workflows/continuous.yml,
            .github/workflows/windows-installer.yml]
  workflow_dispatch:
concurrency: { group: continuous-${{ github.ref }}, cancel-in-progress: true }
permissions: { contents: read }
```

Jobs:

- `build` — `uses: ./.github/workflows/windows-installer.yml` with
  `build-id: main.<short sha>` and `artifact-name: continuous-installer`.
  Runs on PRs too, so a PR that touches packaging proves the frozen build before
  merge (today only a tag or a manual dispatch does).
- `publish` — `needs: build`, `if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'`,
  `permissions: contents: write`:
  1. download artifact; rename to the **stable asset name**
     `cellpy-simple-gui-continuous-setup.exe`; write `SHA256SUMS`.
  2. move the tag: `git tag -f continuous $GITHUB_SHA && git push -f origin continuous`
     (a rolling tag is the one legitimate force-push; `continuous` does not
     match `v*`, so nothing else fires).
  3. `gh release view continuous` → if absent, `gh release create continuous
     --prerelease --title "Latest build from main" --notes-file …`; else
     `gh release upload continuous … --clobber` + `gh release edit continuous
     --notes-file … --prerelease --latest=false`.
  4. Release notes: commit sha + subject + date, the `__version__` it was built
     from, the stable download URL, an explicit "unstable — for the released
     version see *Latest*", and the SmartScreen/upgrade notes linking
     `docs/windows-installer.md`.

`--latest=false` keeps the `/releases/latest` redirect pointing at the real
stable release, so the two download paths stay distinguishable:

- stable: `https://github.com/cellpy/cellpy-simple-gui/releases/latest`
- newest: `https://github.com/cellpy/cellpy-simple-gui/releases/download/continuous/cellpy-simple-gui-continuous-setup.exe`

### 4. Docs

- `docs/releasing.md`: replace the stale "not built on the runner … #124"
  paragraph with the real tag flow (three workflows, one tag), and add a
  short *"Latest build from main"* section (what `continuous` is, how it is
  gated, the one legitimate force-push, how to rehearse via a PR).
- `docs/windows-installer.md`: new *Downloading* section near the top — stable
  vs continuous link, what Add/Remove shows (`0.1.1+main.abc1234`), that
  installing either over the other replaces it.
- `README.md` "Windows installer" bullet: add the two links.
- `packaging/README.md`: one paragraph under the #122 section recording the
  `BuildId`/`VersionInfoVersion` split and why.
- `.issueflows/04-designs-and-guides/`: short `continuous-installer.md`
  (decision: rolling prerelease vs artifacts vs nightly cron; why edit-not-recreate;
  why the tag name must not match `v*`).

## Files to touch

| Path | Change |
|---|---|
| `.github/workflows/windows-installer.yml` | **new** — reusable `workflow_call` build (extracted from `release.yml`) |
| `.github/workflows/continuous.yml` | **new** — push-to-main / PR / dispatch; rolling `continuous` prerelease |
| `.github/workflows/release.yml` | `windows-installer` job → `uses:` the reusable workflow; nothing else |
| `packaging/installer.iss` | optional `BuildId` / `OutputBaseName` defines; `VersionInfoVersion` pinned numeric |
| `packaging/build_installer.ps1` | optional `-BuildId` pass-through |
| `packaging/README.md` | note on display vs resource version |
| `tests/test_packaging.py` | new guards (below) |
| `docs/releasing.md`, `docs/windows-installer.md`, `README.md` | as in §4 |
| `.issueflows/04-designs-and-guides/continuous-installer.md` | **new** design note |
| `.issueflows/01-current-issues/issue168_status.md` | status |

Not touched: `smoke_test.py`, the PyInstaller spec, `entry.py`, `publish.yml`,
`container.yml`, `__init__.py` version.

## Test strategy

Local (`uv run pytest`; the packaging tests carry `@pytest.mark.essential`):

- `installer.iss` text guards (same style as the existing ones):
  `VersionInfoVersion={#AppVersion}` is present verbatim and does **not** use
  `DisplayVersion`; `AppId` unchanged; `OutputBaseFilename` is overridable.
- Workflow guards via `yaml` (PyYAML is already in the env):
  - `continuous.yml` has no `tags:` trigger and its `concurrency` sets
    `cancel-in-progress`; its publish job requires `contents: write` and is
    gated off `pull_request`.
  - The rolling tag name used in `continuous.yml` does **not** match the `v*`
    glob that `release.yml`, `publish.yml`, `container.yml` trigger on
    (parse those three files and assert on their `on.push.tags`).
  - `release.yml` still triggers on `v*` and its `windows-installer` job
    `uses:` the reusable workflow (no silently-forked copy left behind).
- `yaml.safe_load` on all three workflow files (syntax).

In CI, on the PR itself: the new `pull_request` trigger builds and smoke-tests
the real frozen app on `windows-latest` because the PR touches
`packaging/**` and the workflows — that is the actual proof the pipeline
works, and the first rehearsal of `main`'s frozen build since the 2026-08-16
failure. The `publish` job is gated off on PRs, so nothing is released from the
PR. The first real `continuous` release appears on the merge to `main`.

Not testable locally: `ISCC` (Windows-only) — covered by the PR build above.

## Open questions

1. **Trigger cadence.** *Recommended:* every code-affecting push to `main`
   (path-filtered, concurrency-cancelled). Alternative: nightly `cron`
   (predictable cost, but "most recent" lags up to a day and builds when
   nothing changed).
2. **Tag / asset naming.** *Recommended:* tag `continuous`, release title
   "Latest build from main", asset `cellpy-simple-gui-continuous-setup.exe`
   (stable URL). Alternatives: `nightly` (misleading if per-push), `latest`
   (collides with GitHub's own `/releases/latest` wording).
3. **macOS / Linux installers.** The epic ruled these out for now, and the
   reasons still hold: an unsigned macOS `.app` is *refused* by Gatekeeper
   (worse than SmartScreen; notarisation needs a paid Apple developer account),
   and pywebview on Linux needs GTK/WebKit or Qt system packages that a
   PyInstaller bundle cannot carry cleanly. *Recommended:* keep this PR
   Windows-only and open **one follow-up issue** ("macOS/Linux desktop
   bundles: spike") linked from #168 — or treat the existing `uv tool install
   "cellpy-simple-gui[desktop]"` route as the cross-platform answer and say so
   in the docs. Your call; I will not create issues from here.
4. **Should `continuous` also carry the wheel/sdist?** *Recommended:* no — a
   wheel versioned `0.1.1` that is not `0.1.1` is a trap, and `uv tool install
   git+https://github.com/cellpy/cellpy-simple-gui` already serves that need.

Reply **Accept** (with any answers to 1–4; defaults are the recommendations),
**Revise**, or **Abort**. `auto_build = true` will chain into `/iflow-build` on
Accept.
