# Issue #183 — show that the app is starting

## Goal

The windowed Windows app should show a "Starting…" window immediately, before the slow imports, so a first launch (tens of seconds) does not look frozen. Close that window as the real window opens.

## Constraints

- Feedback only. Do not try to make startup faster. The measured cost is Defender on first run (~40–60 s) and importing pandas, polars, pytables, and cellpy after that (~6 s warm). See [packaging/README.md](../../packaging/README.md).
- The splash uses the standard library and `ctypes` only. It must appear before `cellpy_simple_gui.__main__` is imported. It must not be a modal `MessageBox` — that would block the import it is meant to cover.
- No percentage. There is no honest progress value during imports. The window is a message plus a marquee so it looks alive.
- Windowed exe only (`sys.stderr` is missing or not writable — the same situation as the #122 crash dialog). The console exe and `uv run` already have a terminal; they do not get a splash.
- If startup then crashes, close the splash before the existing crash dialog. `close()` is safe to call twice.
- `--server` / `--no-open` do not need a splash. Entry still closes one if it was opened, so a windowed process that falls through cannot leave it up.

### Prior art

- [packaging/entry.py](../../packaging/entry.py) `_show_dialog` — coexist. That box is for a failure and it blocks. The splash is an earlier, non-blocking window with a different title (`Starting cellpy simple GUI`), so it is not the real window (`cellpy simple GUI`).
- [logging_setup.py](../../src/cellpy_simple_gui/logging_setup.py) `_stderr_usable` — same idea (a windowed build has no console). Do not import logging setup from the splash; entry already decides "windowed" before the package's heavy imports.
- [desktop.py](../../src/cellpy_simple_gui/desktop.py) `run_desktop` — the real window is created only after the server is up. Close the splash immediately before `webview.start`.
- [tests/test_packaging.py](../../tests/test_packaging.py) — extend. Those tests already stub the crash dialog and force `sys.stderr = None`. Do not launch a real Win32 window or PyInstaller.
- Toolbox (`.issueflows/00-tools/README.md`): no helper. `graphify-out/GRAPH_REPORT.md` is absent.

## Approach

**`src/cellpy_simple_gui/splash.py`.** Importing it loads only the package `__init__` (the version string). `show()` on Windows starts a daemon thread that opens a small topmost window, centered, with the text "Starting cellpy simple GUI" and "The first launch can take a minute." plus a marquee bar. `close()` posts close and returns. On any other platform, both are no-ops.

**`packaging/entry.py`.** After `freeze_support`, if the process is windowed, `show()`, then import and run the app. `close()` in a `finally`, including when the import itself fails, and before `_report_crash`.

**`desktop.py`.** Call `close()` once the server is up and the webview window has been created, immediately before `webview.start()`.

## Files to touch

- [src/cellpy_simple_gui/splash.py](../../src/cellpy_simple_gui/splash.py) — new. Win32 window, no-op elsewhere.
- [packaging/entry.py](../../packaging/entry.py) — show before the app import; close on the way out and on crash.
- [src/cellpy_simple_gui/desktop.py](../../src/cellpy_simple_gui/desktop.py) — close before `webview.start`.
- [tests/test_packaging.py](../../tests/test_packaging.py) — order and the no-window stubs below.
- [packaging/README.md](../../packaging/README.md) — replace "worth a progress cue" with what the splash actually does.
- [.issueflows/04-designs-and-guides/startup-splash.md](../04-designs-and-guides/startup-splash.md) — the decision, short.

## Test strategy

`uv run pytest` from the worktree. New tests in `tests/test_packaging.py`, with the Win32 calls stubbed:

- A windowed `entry.main` (stderr `None`) calls `show` before the app import, and `close` afterwards.
- A console `entry.main` does not call `show`.
- A crash after `show` still calls `close`, then the existing dialog.
- `splash.show` / `splash.close` on a non-Windows platform do not touch `ctypes`.

No frozen exe in CI here. The tests lock the order, which is the part that makes the window appear during the slow import.

## Open questions

- None that block this. Accept builds the windowed-exe splash above. Revise if the splash should also appear for a normal `uv run` desktop launch.
