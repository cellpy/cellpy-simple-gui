"""Entry point.

    cellpy-simple-gui            -> open in a native desktop window (default)
    cellpy-simple-gui --server   -> just run the local server, open the browser
    cellpy-simple-gui --no-open  -> run the server without opening anything
"""

from __future__ import annotations

import argparse
import webbrowser

from .config import get_settings
from .server import ServerThread, pick_port


def main() -> None:
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

            run_desktop()
            return
        except Exception as exc:  # noqa: BLE001 - fall back to browser mode
            print(f"Desktop window unavailable ({exc}); falling back to browser mode.")

    port = pick_port(settings.host, args.port or settings.port)
    server = ServerThread(settings.host, port)
    server.start(wait=True)
    print(f"\n  {settings.app_name} running at:\n    {server.url}\n")
    if not args.no_open:
        webbrowser.open(server.url)
    try:
        server._thread.join()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
