# Plan: Issue #13 — add workflows

## Goal

Mark critical tests `essential` and add GitHub Actions that run them on code changes, plus a same-named docs mock workflow so PR checks stay green on doc-only PRs.

## Approach

1. Register a pytest `essential` marker; decorate the critical smoke/unit tests.
2. Add `.github/workflows/essential-tests.yml` — path-filtered to code; runs `uv run pytest -m essential`.
3. Add `.github/workflows/essential-tests-docs.yml` — same workflow/job names; `paths-ignore` for those code paths; no-op success step.

## Files to touch

- `pyproject.toml`
- `tests/**/*.py` (markers only)
- `.github/workflows/essential-tests.yml`
- `.github/workflows/essential-tests-docs.yml`

## Test strategy

`uv run pytest -m essential` locally, then full `uv run pytest`.
