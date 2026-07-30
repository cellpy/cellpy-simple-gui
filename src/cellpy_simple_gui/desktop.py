"""Desktop shell: run the local app inside a native window via pywebview."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from .config import get_settings
from .server import ServerThread, pick_port

log = logging.getLogger(__name__)

# Packaged raster for the native window (Windows prefers .ico; GTK/Qt/Cocoa accept it too).
_WINDOW_ICON = (
    Path(__file__).resolve().parent / "web" / "static" / "img" / "cellpy-icon.ico"
)


def _close_webview_windows(webview) -> None:
    """Destroy open windows so webview.start() can return."""
    log.info("Ctrl+C received; closing desktop window")
    for win in list(getattr(webview, "windows", []) or []):
        try:
            win.destroy()
        except Exception:  # noqa: BLE001 - best-effort shutdown
            pass


def _install_ctrl_c_close(webview) -> tuple[object, object | None]:
    """Make Ctrl+C close the native window (SIGINT alone often never fires in the GUI loop).

    Returns (previous_sigint_handler, win32_handler_keep_alive).
    """
    previous = signal.signal(
        signal.SIGINT, lambda *_: _close_webview_windows(webview)
    )
    win32_handler = None
    if sys.platform == "win32":
        # Console Ctrl+C is delivered via SetConsoleCtrlHandler while the main
        # thread is blocked in native GUI code — Python's SIGINT handler may not run.
        import ctypes
        from ctypes import wintypes

        HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
        CTRL_C_EVENT, CTRL_BREAK_EVENT = 0, 1

        @HandlerRoutine
        def win32_handler(ctrl_type: int) -> bool:
            if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT):
                _close_webview_windows(webview)
                # Failsafe: if the GUI loop never unwinds, free the console anyway.
                threading.Thread(
                    target=lambda: (time.sleep(2.0), os._exit(0)),
                    name="csg-ctrlc-exit",
                    daemon=True,
                ).start()
                return True
            return False

        ctypes.windll.kernel32.SetConsoleCtrlHandler(win32_handler, True)
    return previous, win32_handler


def _shutdown_background(server: ServerThread) -> None:
    """Stop jobs + uvicorn so the process can exit and free the terminal."""
    try:
        from .api.jobs import get_job_manager

        get_job_manager().shutdown()
    except Exception:  # noqa: BLE001 - exit path must not raise
        log.exception("Job manager shutdown failed")
    try:
        server.stop()
    except Exception:  # noqa: BLE001
        log.exception("Server stop failed")


def run_desktop() -> None:
    import webview  # pywebview

    settings = get_settings()
    port = pick_port(settings.host, settings.port)
    server = ServerThread(settings.host, port)
    server.start(wait=True)
    log.info("Desktop server ready at %s", server.url)

    webview.create_window(
        settings.app_name,
        server.url,
        width=1360,
        height=900,
        min_size=(1024, 680),
        background_color="#0f1420",
    )
    previous, _win32_keepalive = _install_ctrl_c_close(webview)
    icon = str(_WINDOW_ICON) if _WINDOW_ICON.is_file() else None
    try:
        webview.start(icon=icon)
    finally:
        signal.signal(signal.SIGINT, previous)
        if sys.platform == "win32" and _win32_keepalive is not None:
            import ctypes

            ctypes.windll.kernel32.SetConsoleCtrlHandler(_win32_keepalive, False)
        log.info("Closing desktop window; stopping server")
        _shutdown_background(server)
        # Hard-exit: daemon job workers + pywebview/native threads can otherwise
        # leave the Cursor/terminal session wedged with no prompt.
        try:
            sys.stderr.flush()
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass
        os._exit(0)


if __name__ == "__main__":
    run_desktop()
