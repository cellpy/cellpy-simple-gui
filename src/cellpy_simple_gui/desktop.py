"""Desktop shell: run the local app inside a native window via pywebview."""

from __future__ import annotations

from .config import get_settings
from .server import ServerThread, pick_port


def run_desktop() -> None:
    import webview  # pywebview

    settings = get_settings()
    port = pick_port(settings.host, settings.port)
    server = ServerThread(settings.host, port)
    server.start(wait=True)

    window = webview.create_window(
        settings.app_name,
        server.url,
        width=1360,
        height=900,
        min_size=(1024, 680),
        background_color="#0f1420",
    )
    try:
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    run_desktop()
