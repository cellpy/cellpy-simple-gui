# Plan: Issue #19 — journal load error surfacing

## Goal

Corrupt / failing batch journals must not leave the UI spinning with no feedback — surface cellpy exceptions as user-visible errors.

## Approach

1. Clarify exceptions in `load_journal_cells` (parse failures; load failures that yield no cells).
2. Catch in `_load_journal_job` and return `{added:[], errors:[…]}` so SSE always completes with a toastable result.
3. Toast on job-submit failures in `runJob`.
4. Add a regression test for a corrupt journal.

## Test strategy

`uv run pytest` including new journal error test.
