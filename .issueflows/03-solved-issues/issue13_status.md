# Status: Issue #13 — add workflows

- [x] Done

## Done

- Registered pytest marker `essential` and marked critical API/core/files/ingest/projects tests.
- Added `Essential tests` workflow (real `pytest -m essential` on code paths).
- Added matching document mock flow workflow (`paths-ignore`) so the same check stays green on docs-only changes.
