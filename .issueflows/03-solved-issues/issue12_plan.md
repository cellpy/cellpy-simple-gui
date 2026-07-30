# Plan: Issue #12 — add logging

## Goal

Add nice terminal logging (loguru) so startup and runtime events are readable in the console.

## Approach

1. Add `loguru` dependency.
2. Add a small `logging_setup` helper that configures loguru (colorized stderr, sensible level) and bridges stdlib `logging` into it.
3. Call setup from `__main__.main()` before the app starts; replace bare `print` startup messages with loguru.
4. Keep existing `logging.getLogger` call sites — they flow through the bridge.

## Files to touch

- `pyproject.toml` / `uv.lock`
- `src/cellpy_simple_gui/logging_setup.py` (new)
- `src/cellpy_simple_gui/__main__.py`
- `.issueflows/01-current-issues/issue12_*`

## Test strategy

`uv run pytest` — no behaviour change to API; setup is side-effect at CLI entry only.
