# Issue #183 status

- [x] Done

## What's done

- The windowed Windows exe opens a Starting… window before importing the app, and closes it as the real window opens. `--server` and a desktop fallback close it too. A crash closes it before the existing error dialog.
- No splash when a console is readable, and no splash on non-Windows.
- Packaging tests lock that order. `uv run pytest` passed.
- Decision recorded in `startup-splash.md`.

## Remaining work

- None. The native window itself was not shown here; this machine is Linux, and the Win32 calls are covered by the no-op and order tests.
