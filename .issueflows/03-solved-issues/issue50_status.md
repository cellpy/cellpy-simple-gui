# Issue #50 — Status

Interactive `/iflow-fix` session.

- [x] Done

## Iterative fixes log

- 2026-07-30: Journal-load logging — INFO around `from_journal` / `batch.load()` / linkable counts / per-cell library add; clearer job progress messages so stale hangs show which step is stuck.
- 2026-07-30: “Add cellpy files” collapsed behind a disclosure toggle (same pattern as Import raw).
- 2026-07-30: Ctrl+C closes the app — desktop destroys the pywebview window (SIGINT + Win32 console handler); server mode uses timed join so KeyboardInterrupt is prompt.
- 2026-07-30: Journal load hang diagnosis — per-cell progress + pre/post INFO (path, outcome, timing); `LoadPolicy(CELLPY_ONLY)` so raw lab-share paths can’t stall forever; project-open logs each cell too.
- 2026-07-30: Desktop exit frees the terminal — daemon job workers, job-manager shutdown, uvicorn stop+join, `os._exit(0)` after window close / Ctrl+C failsafe.
- 2026-07-31: Silence uvicorn lifespan `CancelledError` on window close (`lifespan="off"`).

## Remaining work

- None — landed via `/iflow-close`.
