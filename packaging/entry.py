"""Frozen-app entry point.

A module of its own rather than pointing PyInstaller at ``__main__.py``: the
frozen process has no ``-m`` semantics, and multiprocessing needs the freeze
support call before anything else touches threads.

It also owns the last-resort crash handler. The #117 spike found that the only
reason a broken bundle was diagnosable at all was ``console=True`` — the failure
was ``ModuleNotFoundError`` at import, and a windowed build would have shown
nothing whatsoever. The installer ships a windowed exe, so that diagnosability
has to be replaced rather than dropped: a log file, and a dialog that says where
it is (#122).
"""

from __future__ import annotations

import multiprocessing
import sys
import traceback
from pathlib import Path

APP_NAME = "cellpy simple GUI"


def _log_dir() -> Path:
    """Where to write a crash report, using stdlib only.

    Duplicated from ``cellpy_simple_gui.logging_setup.log_dir`` on purpose: the
    failure being reported may well *be* an import failure, so this path must
    not depend on the package importing successfully. There is a test asserting
    the two agree.
    """
    import os

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / "cellpy-simple-gui" / "logs"


def _show_dialog(message: str) -> None:
    """Native message box. Separate so tests can stub it — calling the real one
    would block on a modal window nobody is there to dismiss."""
    try:
        import ctypes

        # MB_ICONERROR | MB_SETFOREGROUND
        ctypes.windll.user32.MessageBoxW(
            None, message, f"{APP_NAME} — startup failed", 0x10 | 0x10000
        )
    except Exception:  # noqa: BLE001 - not Windows, or no window station: give up
        pass


def _report_crash(exc: BaseException) -> None:
    """Write the traceback somewhere findable, and say so if there is a UI."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    target: Path | None = None
    try:
        directory = _log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "startup-error.log"
        target.write_text(text, encoding="utf-8")
    except OSError:
        target = None

    # If there is a console, the traceback is the most useful thing to print.
    if getattr(sys, "stderr", None) is not None:
        try:
            sys.stderr.write(text)
            return
        except Exception:  # noqa: BLE001 - fall through to the dialog
            pass

    # Windowed build: a dialog is the only channel the user has.
    where = f"\n\nDetails were written to:\n{target}" if target else ""
    _show_dialog(
        f"{APP_NAME} could not start.\n\n"
        f"{type(exc).__name__}: {exc}"
        f"{where}\n\n"
        "Running cellpy-simple-gui-console.exe from the install folder will "
        "show the full error."
    )


def main() -> int:
    # Without this, a frozen child process re-runs the whole app instead of the
    # worker function. polars/pyarrow may spawn; cheap insurance either way.
    multiprocessing.freeze_support()
    try:
        from cellpy_simple_gui.__main__ import main as app_main

        return app_main() or 0
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - this is the last line of defence
        _report_crash(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
