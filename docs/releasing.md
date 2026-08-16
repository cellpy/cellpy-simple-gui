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

The tag triggers:

| workflow | artefact |
|---|---|
| `publish.yml` | sdist + wheel → PyPI |
| `container.yml` | image → `ghcr.io/cellpy/cellpy-simple-gui` |

The publish job **refuses to run if the tag and `__version__` disagree**, because
a wrong version cannot be corrected after upload.

The Windows installer is not built on the runner — it needs Inno Setup and is
produced locally with `pwsh packaging/build_installer.ps1`, then attached to the
GitHub release by hand. Automating that is #124.

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
