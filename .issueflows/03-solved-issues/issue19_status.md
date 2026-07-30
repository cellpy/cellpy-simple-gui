# Status: Issue #19 — journal load errors

- [x] Done

## Done

- Clearer RuntimeError messages from `load_journal_cells` (parse / load failures).
- `_load_journal_job` catches failures and returns toastable `{added, errors}`.
- `runJob` toasts when a job fails to start.
- Tests for corrupt journal (adapter + API job result).
