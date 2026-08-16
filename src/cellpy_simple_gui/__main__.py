"""Entry point.

    cellpy-simple-gui            -> open in a native desktop window (default)
    cellpy-simple-gui --server   -> just run the local server, open the browser
    cellpy-simple-gui --no-open  -> run the server without opening anything
    cellpy-simple-gui --dev      -> developer mode (also via CSG_DEV_MODE=1)
"""

from __future__ import annotations

import argparse
import os
import webbrowser
from pathlib import Path

from loguru import logger

from .config import get_settings
from .logging_setup import setup_logging
from .server import ServerThread, pick_port


#: cellpy path settings this app pins down at startup, and the env var each one
#: is overridden with. Only directories cellpy *writes* to, and only ones whose
#: default is relative — see ``_anchor_cellpy_paths``.
_CELLPY_DIRS = (
    ("examplesdir", "CELLPY_PATHS__EXAMPLESDIR"),
    ("filelogdir", "CELLPY_PATHS__FILELOGDIR"),
)


def _anchor_cellpy_paths() -> None:
    """Give cellpy's writable directories an absolute home before it picks one.

    Several ``paths`` defaults are **relative** (``cellpy_data\\examples``,
    ``cellpy_data\\logs``) and cellpy resolves them against the process cwd. For
    an installed app the cwd is wherever the Start-menu shortcut happened to
    leave it — the install folder — so cellpy writes demo data and debug logs
    into the application directory. Measured on the real install (#122): a first
    run put ~9 MB of demo data and three log files there, and the demo data
    survived the uninstall because the installer had never put it there.

    ``examplesdir`` has a second failure on top. ``cellpy.utils.example_data``
    resolves its data path **at import time** and, when the directory does not
    exist, silently falls back inside cellpy's own package — read-only in a
    container, install-owned when frozen. So these are created, not just
    resolved, and this runs before anything imports ``example_data``.

    A relative value is anchored at the user's home; an absolute one is left
    exactly as the user wrote it. That makes this a disambiguation rather than
    an override. Values that are not local paths at all (``rawdatadir`` can be
    an ``scp://`` URL) are never touched.

    Upstream would rather default to absolute paths and create the directories
    (cellpy#938).
    """
    try:
        from cellpy import config as cellpy_config

        changed = False
        for field, env_var in _CELLPY_DIRS:
            raw = str(getattr(cellpy_config.get_config().paths, field, "") or "")
            if not raw or "://" in raw:  # not a local path; leave it alone
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = (Path.home() / path).resolve()
                os.environ[env_var] = str(path)
                changed = True
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.debug("Could not create cellpy {}: {}", field, exc)
            logger.debug("cellpy {} -> {}", field, path)

        if changed:
            # Without this the env overrides are set but unread, and
            # example_data still resolves its own path against the cwd.
            cellpy_config.reload()
    except Exception as exc:  # noqa: BLE001 - never block startup over this
        logger.debug("Could not prepare cellpy directories: {}", exc)


def main() -> None:
    setup_logging()
    _anchor_cellpy_paths()

    parser = argparse.ArgumentParser(prog="cellpy-simple-gui")
    parser.add_argument(
        "--server", action="store_true", help="run as a plain local web server"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="do not open a browser/window"
    )
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="developer mode: every cellpy plot family and the higher batch limits",
    )
    args = parser.parse_args()

    # Settings read the environment and are cached, so this must land before the
    # first get_settings() call (setup_logging above does not read them).
    if args.dev:
        os.environ["CSG_DEV_MODE"] = "1"
        get_settings.cache_clear()

    settings = get_settings()
    if settings.dev_mode:
        logger.warning("DEVELOPER MODE — unrestricted plot families and batch limits")

    if not args.server:
        try:
            from .desktop import run_desktop

            logger.info("Starting desktop window")
            run_desktop()
            return
        except ImportError:
            # pywebview lives in the [desktop] extra (#118). A bare ImportError
            # here reads as a bug; say what to install instead.
            logger.warning(
                "No desktop support installed (pywebview); falling back to "
                "browser mode. Install it with: uv sync --extra desktop"
            )
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
