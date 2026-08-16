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

Then check it installs:

```bash
uv tool install --index https://test.pypi.org/simple/ \
  --index-strategy unsafe-best-match "cellpy-simple-gui[desktop]"
```

(The extra index flags are needed because the dependencies live on real PyPI,
not TestPyPI.)

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
