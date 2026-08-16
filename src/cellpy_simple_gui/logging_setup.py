"""Terminal logging via loguru, with a stdlib logging bridge."""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections import deque
from pathlib import Path

from loguru import logger


def log_dir() -> Path:
    """Where a windowed build writes its log, resolved without app config.

    Deliberately free of any dependency on :mod:`.config`: this is also the
    place a *startup* failure gets recorded, and importing settings may be the
    thing that failed. Plain stdlib, no imports that can raise.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / "cellpy-simple-gui" / "logs"


def _stderr_usable() -> bool:
    """False in a windowed PyInstaller build, where there is no console.

    ``sys.stderr`` is ``None`` there, and handing that to ``logger.add`` raises
    — which would kill the app during logging setup, before it can report
    anything. That is the exact failure a windowed build is prone to, so it is
    checked rather than assumed (#122).
    """
    stream = getattr(sys, "stderr", None)
    if stream is None:
        return False
    try:
        stream.write("")
        return True
    except Exception:  # noqa: BLE001 - a broken handle is just as unusable
        return False

#: Recent log records, for the developer-mode viewer (#97). Bounded, so a long
#: session cannot grow it without limit; the terminal/file sinks stay the record
#: of truth.
_RING: deque[dict] = deque(maxlen=2000)
_RING_LOCK = threading.Lock()
_RING_ID: int | None = None
_RING_WANTED = False


def _ring_sink(message) -> None:
    record = message.record
    with _RING_LOCK:
        _RING.append(
            {
                "time": record["time"].isoformat(timespec="milliseconds"),
                "level": record["level"].name,
                "name": record["extra"].get("logger_name") or record["name"],
                "message": record["message"],
            }
        )


def enable_ring_buffer(level: str = "DEBUG") -> None:
    """Start capturing records for the in-app viewer (idempotent).

    Also installs the stdlib bridge when it is missing: without it only loguru's
    own records arrive and the viewer sits empty exactly when it matters, since
    cellpy logs through stdlib.
    """
    global _RING_ID, _RING_WANTED

    _RING_WANTED = True
    if _RING_ID is not None:
        return
    if not any(isinstance(h, _InterceptHandler) for h in logging.getLogger().handlers):
        logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    _RING_ID = logger.add(_ring_sink, level=level, backtrace=False, diagnose=False)


def recent_logs(limit: int = 500, level: str | None = None) -> list[dict]:
    """Newest-last slice of the ring, optionally filtered to a minimum level."""
    order = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
    with _RING_LOCK:
        records = list(_RING)
    if level:
        wanted = level.upper()
        if wanted in order:
            floor = order.index(wanted)
            records = [
                r for r in records
                if r["level"] in order and order.index(r["level"]) >= floor
            ]
    return records[-max(1, limit):]


def ring_enabled() -> bool:
    return _RING_ID is not None


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        # Carry the originating logger name through: loguru's own ``name`` ends
        # up as "logging" for bridged records, which tells the viewer nothing.
        logger.opt(depth=depth, exception=record.exc_info).bind(
            logger_name=record.name
        ).log(level, record.getMessage())


def setup_logging(level: str | None = None) -> None:
    """Configure colorized loguru output on stderr and intercept stdlib logging.

    Level comes from ``level``, else ``CSG_LOG_LEVEL``, else ``INFO``.
    Safe to call more than once — sinks are replaced each time.
    """
    global _RING_ID

    resolved = (level or os.environ.get("CSG_LOG_LEVEL") or "INFO").upper()
    logger.remove()
    _RING_ID = None  # logger.remove() dropped the ring sink along with the rest

    if _stderr_usable():
        logger.add(
            sys.stderr,
            level=resolved,
            colorize=True,
            backtrace=False,
            diagnose=False,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan> - <level>{message}</level>"
            ),
        )
    else:
        # A windowed build has nowhere to print. Without a file sink the app
        # would run with logging silently discarded, and a support request
        # would have nothing to attach.
        try:
            directory = log_dir()
            directory.mkdir(parents=True, exist_ok=True)
            logger.add(
                directory / "app.log",
                level=resolved,
                rotation="2 MB",
                retention=3,
                backtrace=False,
                diagnose=False,
                encoding="utf-8",
            )
        except OSError:
            # Nowhere to write is not a reason to refuse to start.
            pass

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    if _RING_WANTED:
        enable_ring_buffer()
