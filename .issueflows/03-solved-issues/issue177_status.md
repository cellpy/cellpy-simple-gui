# Status — Issue #177

- [x] Done

## What's done

- 2026-10-03 — Accepted layout **A (Quiet lab)**. Screenshots are in scope.
- Chrome in `app.css`: neutral tokens, solid top bar, flat teal primary, compact controls.
- Figure theme tokens and the desktop window background follow the same neutrals, so Match app does not leave a blue plot in a gray shell.
- Recaptured `docs/img` (PNG gallery and `demo.gif`) against that chrome. Light shot uses Group avg + Spread.
- Regenerated `llms-full.txt` so it matches the README heading (`Some examples`). `uv run --extra dev pytest`: the previous `test_llms_full_txt_is_current` failure is gone; `tests/test_agent_docs.py` passes. Full suite before that regen was 357 passed, 6 skipped, 1 failed.

## Remaining work

- None.
