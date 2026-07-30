# Journal load diagnostics & desktop exit

From issue #50 (`/iflow-fix`).

## Journal / project load

- Drive cellpy journal loads with **pre- and post-cell** INFO logs (label + `.cellpy` path + outcome/timing). cellpy’s own `on_progress` only fires *after* each cell, so a hang looks silent without our own loop.
- Use `LoadPolicy(source=CELLPY_ONLY)` for GUI journal import so old journals with dead lab-share `raw_file_names` do not stall forever.
- Wire the same progress hook into the job UI so the bar advances per cell.
- Project open logs each cell path the same way.

## Desktop exit / terminal prompt

- Job pool workers must be **daemon** threads; a stuck cellpy load must not pin the process after the window closes.
- On window close: shut down the job manager (`wait=False`), stop uvicorn (`should_exit` + short join), then `os._exit(0)` so pywebview/native leftovers cannot wedge the Cursor terminal.
- Ctrl+C: destroy the pywebview window (SIGINT + Win32 `SetConsoleCtrlHandler`); 2s failsafe `os._exit` if the GUI loop never unwinds.
- Uvicorn `lifespan="off"` — we have no FastAPI lifespan hooks; lifespan `"on"` prints a scary `CancelledError` traceback on every forced stop.
