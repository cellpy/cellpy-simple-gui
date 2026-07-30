"""Entry point.

    cellpy-simple-gui            -> open in a native desktop window (default)
    cellpy-simple-gui --server   -> just run the local server, open the browser
    cellpy-simple-gui --no-open  -> run the server without opening anything
"""

from __future__ import annotations

import argparse
import webbrowser

from loguru import logger

from .config import get_settings
from .logging_setup import setup_logging
from .server import ServerThread, pick_port


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(prog="cellpy-simple-gui")
    parser.add_argument(
        "--server", action="store_true", help="run as a plain local web server"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="do not open a browser/window"
    )
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()

    if not args.server:
        try:
            from .desktop import run_desktop

            logger.info("Starting desktop window")
            run_desktop()
            return
        except Exception as exc:  # noqa: BLE001 - fall back to browser mode
            logger.warning(
                "Desktop window unavailable ({}); falling back to browser mode.",
                exc,
            )

    port = pick_port(settings.host, args.port or settings.port)
    server = ServerThread(settings.host, port)
    server.start(wait=True)
    logger.info("{} running at {}", settings.app_name, server.url)
    if not args.no_open:
        webbrowser.open(server.url)
    try:
        # Timed joins so Ctrl+C is delivered promptly (bare join can stall on Windows).
        while server._thread.is_alive():
            server._thread.join(timeout=0.5)
    except KeyboardInterrupt:
        logger.info("Shutting down")
        try:
            from .api.jobs import get_job_manager

            get_job_manager().shutdown()
        except Exception:  # noqa: BLE001
            pass
        server.stop()


if __name__ == "__main__":
    main()
