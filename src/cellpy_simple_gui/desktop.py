"""Desktop shell: run the local app inside a native window via pywebview."""

from __future__ import annotations

from pathlib import Path

from .config import get_settings
from .server import ServerThread, pick_port

# Packaged raster for the native window (Windows prefers .ico; GTK/Qt/Cocoa accept it too).
_WINDOW_ICON = (
    Path(__file__).resolve().parent / "web" / "static" / "img" / "cellpy-icon.ico"
)


def run_desktop() -> None:
    import webview  # pywebview

    settings = get_settings()
    port = pick_port(settings.host, settings.port)
    server = ServerThread(settings.host, port)
    server.start(wait=True)

    webview.create_window(
        settings.app_name,
        server.url,
        width=1360,
        height=900,
        min_size=(1024, 680),
        background_color="#0f1420",
    )
    icon = str(_WINDOW_ICON) if _WINDOW_ICON.is_file() else None
    try:
        webview.start(icon=icon)
    finally:
        server.stop()


if __name__ == "__main__":
    run_desktop()
