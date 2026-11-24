# Starting window (issue #183)

The windowed Windows exe has no console. First launch spends tens of seconds
in Defender and imports before any window exists, so it looks frozen.

**Decision:** `cellpy_simple_gui.splash` opens a small topmost window
("Starting cellpy simple GUI" / "The first launch can take a minute." plus a
marquee) from `packaging/entry.py` *before* importing the app, and only when
stderr is missing or not writable. `desktop.run_desktop` closes it immediately
before `webview.start`. The `--server` path and a desktop fallback close it too,
so it cannot outlive the wait. A crash closes it before the existing error dialog.

No percentage: import time has no honest progress. No attempt to make the
imports faster. The console exe and `uv run` already have a terminal, so they
get no splash.

Alternative considered: a modal `MessageBox` in the entry point. Rejected
because it would block the import it is meant to cover.
