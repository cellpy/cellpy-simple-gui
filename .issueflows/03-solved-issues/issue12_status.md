# Status: Issue #12 — add logging

- [x] Done

## Done

- Added `loguru` dependency and `logging_setup.setup_logging()` (colorized stderr + stdlib bridge).
- Wired setup into `__main__.main()`; replaced startup `print`s with loguru.
- Level via `CSG_LOG_LEVEL` (default `INFO`).
