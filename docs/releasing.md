# Releasing

Three artefacts come out of one tag: a **PyPI package**, a **container image**,
and a **Windows installer**. This page covers the one-time setup and the routine.

---

## One-time: let PyPI trust this repository

This has to be done by the person who will own the project on PyPI — it needs a
logged-in PyPI account, so it cannot be automated from here.

The package uses **trusted publishing** (OIDC): GitHub proves the workflow's
identity to PyPI directly, so there is no API token to create, store, rotate or
leak. Nothing secret is ever pasted into this repository.

The name `cellpy-simple-gui` was unclaimed when this was written, so the first
publish also claims it. Because the project does not exist yet, PyPI calls this
a **pending publisher**.

1. Sign in to <https://pypi.org> as the owning account (**jepe**).
2. Go to **Your account → Publishing**
   (<https://pypi.org/manage/account/publishing/>).
3. Under *Add a new pending publisher*, choose **GitHub** and fill in:

   | field | value |
   |---|---|
   | PyPI Project Name | `cellpy-simple-gui` |
   | Owner | `cellpy` |
   | Repository name | `cellpy-simple-gui` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The owner is the **GitHub org**, not your PyPI username — trusted publishing
   binds to a repository, while the PyPI project stays owned by your account.

4. Repeat on <https://test.pypi.org> with environment name `testpypi` if you
   want the rehearsal below. Worth it for a first publish.

5. In this repository, create the matching **environments**: GitHub → Settings →
   Environments → *New environment* → `pypi` (and `testpypi`). Leaving them
   empty is fine; the value is that you can later add a required reviewer, so a
   release waits for a human click.

> **Why the environment name matters.** PyPI checks it. If the workflow's
> `environment:` and the pending publisher disagree, the upload is rejected —
> which is the failure mode to expect on a first attempt.

---

## One-time: make the container image public

A **new GHCR package is private by default**, even from a public repository. The
push succeeds and the workflow goes green, so nothing looks wrong from the
inside — but everyone else gets:

```
$ docker pull ghcr.io/cellpy/cellpy-simple-gui
Error response from daemon: ... unauthorized
```

which reads like a broken image rather than a permissions setting. Confirmed the
boring way after the 0.1.0 release: a known-public GHCR image pulled anonymously
from the same machine, ours did not.

After the first tagged release: GitHub → the org's **Packages** →
`cellpy-simple-gui` → **Package settings** → *Danger Zone* → **Change
visibility** → Public.

**If "Public" is greyed out** — *"Setting is disabled by organization
administrators"* — the org forbids public packages, and no amount of clicking on
the package page will help. An org **owner** has to allow it first:

> `https://github.com/organizations/<org>/settings/packages` → **Package
> creation** → tick **Public**

then return to the package's visibility dialog. This is what happened on the
0.1.0 release.

Only needed once; subsequent pushes inherit the package's visibility.

---

## Rehearse on TestPyPI

Optional but recommended before the very first release, because a version
number on PyPI can never be reused — not even after deleting it.

GitHub → Actions → **Publish to PyPI** → *Run workflow* → target `testpypi`.

Then check the *published artifact* installs. Fetch the wheel from TestPyPI by
URL and install that:

```bash
python - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen(
    "https://test.pypi.org/pypi/cellpy-simple-gui/json"))
url = next(u["url"] for u in d["urls"] if u["packagetype"] == "bdist_wheel")
print(url)
PY
# then, with that URL:
uv tool install "<downloaded-wheel>[desktop]"
```

> **Do not point uv at the TestPyPI index for the dependencies.** The obvious
> command —
> `uv tool install --index https://test.pypi.org/simple/ --index-strategy unsafe-best-match ...`
> — fails, and not because of anything wrong with our package:
>
> ```
> × Failed to build `fastapi==1.0`
>   help: `fastapi` (v1.0) was included because `cellpy-simple-gui` (v0.1.0)
>         depends on `fastapi>=0.115`
> ```
>
> TestPyPI's namespace is full of placeholder uploads, including a bogus
> `fastapi==1.0` that uv prefers over the real one. Installing the wheel
> directly resolves dependencies from real PyPI and tests the thing we actually
> published.

Worth comparing the downloaded file's SHA-256 against the `digests.sha256` in
that JSON — it confirms you are testing the bytes the index is serving.

---

## Cutting a release

1. Bump the version in **`src/cellpy_simple_gui/__init__.py`**. That is the only
   place it lives — `pyproject.toml` reads it from there, so the two cannot
   drift.
2. Commit, then tag and push:

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

The tag triggers three workflows:

| workflow | artefact |
|---|---|
| `publish.yml` | sdist + wheel → PyPI |
| `container.yml` | image → `ghcr.io/cellpy/cellpy-simple-gui` |
| `release.yml` | Windows installer, the same installer as a `.zip`, sdist + wheel + `SHA256SUMS` → the GitHub Release |

The publish job **refuses to run if the tag and `__version__` disagree**, because
a wrong version cannot be corrected after upload.

The Windows installer is built on a `windows-latest` runner by
`.github/workflows/windows-installer.yml` — PyInstaller, then the 15-check
`packaging/smoke_test.py` against the frozen app, then Inno Setup — and only
reaches the release if the smoke test passes (#124). The same recipe is what
`pwsh packaging/build_installer.ps1` runs locally.

To rehearse without burning a version number: Actions → **Release** → *Run
workflow* with `ref: main`. From a branch it builds and smoke-tests everything
and stops short of creating a release.

---

## The rolling `continuous` release

Between tags, the newest `main` is still downloadable: every push to `main` that
touches code (`src/`, `packaging/`, `pyproject.toml`, `uv.lock`,
`.python-version`, or the two workflows) runs `.github/workflows/continuous.yml`,
which builds and smoke-tests the installer exactly as a release would and then
refreshes **one** prerelease under the tag **`continuous`** (#168):

- Title *Latest build from main*, marked **pre-release**, never *Latest* — so
  `/releases/latest` keeps pointing at the real release.
- Asset name is fixed, so the download link never changes:
  `https://github.com/cellpy/cellpy-simple-gui/releases/download/continuous/cellpy-simple-gui-continuous-setup.exe`
- *Add or remove programs* shows `0.1.1+main.abc1234` — the released version it
  was built on, plus the commit. The Win32 version resource stays `0.1.1`,
  because it has to be numeric.
- The release is **edited, not recreated**: assets are replaced with
  `--clobber`, notes rewritten, the tag moved. Creating a release notifies
  everyone watching releases; editing one does not, and this one changes
  several times a day.
- A red smoke test publishes nothing and leaves the previous continuous
  installer where it was.

Two things about it that are deliberately unusual:

**The tag is force-pushed.** `continuous` is a pointer to "whatever `main` last
built", not history, so `git push --force origin refs/tags/continuous` is the
mechanism — the one legitimate force-push in this repository. Its name must
never match the `v*` glob the three release workflows trigger on, or every
merge would publish to PyPI and GHCR; `tests/test_packaging.py` pins that.

**PRs build it too.** A pull request that touches `packaging/` or either
workflow runs the Windows build and smoke test — and stops before publishing.
That is how a change to the packaging recipe is proved *before* it lands,
rather than on the next tag. Docs-only merges skip the build entirely.

---

## What to check after publishing

```bash
uv tool install "cellpy-simple-gui[desktop]"
cellpy-simple-gui
```

The smoke test drives the installed executable through the same 15 checks CI
runs against the container and the frozen build:

```bash
uv run python packaging/smoke_test.py "$(command -v cellpy-simple-gui)"
```

Worth doing on a machine that is not the one you released from.

---

## Things that will bite

**A version number is permanent.** PyPI never allows a version to be reused,
even after you delete the release. A mistake means burning a version number and
publishing the next one.

**`uv tool install` picks the newest Python it can find**, not the one you
develop on. That is not hypothetical: it installed on 3.14 and every background
job raised `AttributeError`, because the job pool had copied a private CPython
function whose signature changed in 3.14 — while the whole test suite was green
on 3.13. The `newest-python` CI job exists to catch the next one.

**The `desktop` extra is not installed by default.** `uv tool install
cellpy-simple-gui` gives a working app that opens in a browser;
`cellpy-simple-gui[desktop]` gives the native window.

**TestPyPI is not a mirror.** Its package namespace is separate and full of
placeholder uploads, so resolving *dependencies* there gives nonsense. Only ever
pull our own artifact from it — see the rehearsal section above.

---

## Rehearsal log

**2026-08-16, 0.1.0 → TestPyPI.** First run of the whole path. Build, `twine
check` and the web-asset assertion passed; the upload succeeded, so the trusted
publisher and environment names line up. `publish (PyPI)` correctly skipped.

The published wheel's SHA-256 matched the file served by the index, and the
installed executable passed all 15 smoke checks on Python 3.14 against a fresh
profile.

One thing went wrong, and it was the documentation rather than the package: the
install command originally written here pointed uv at the TestPyPI index for
everything and died on a fake `fastapi==1.0`. Corrected above.

**2026-08-16, 0.1.0 → PyPI and GHCR.** First real release.

`cellpy-simple-gui 0.1.0` is on PyPI. The wheel's SHA-256 is **byte-identical to
the TestPyPI upload** — same source, same result, which is a pleasant thing to be
able to check. `uv tool install "cellpy-simple-gui[desktop]"` works with no index
flags, and the installed executable passed 15/15 smoke checks on a fresh profile.

The container pushed to GHCR as `0.1.0`, `0.1` and `latest`, but landed
**private** — see the visibility section above. Nothing in the release looked
wrong from the inside; it was caught by trying an anonymous
`docker manifest inspect` and confirming against a known-public image that it was
a permissions setting rather than a broken push. Worth repeating that check after
any first release to a new registry.
