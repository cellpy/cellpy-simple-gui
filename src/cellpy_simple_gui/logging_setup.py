"""Terminal logging via loguru, with a stdlib logging bridge."""

from __future__ import annotations

import logging
import os
import sys

from loguru import logger


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
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: str | None = None) -> None:
    """Configure colorized loguru output on stderr and intercept stdlib logging.

    Level comes from ``level``, else ``CSG_LOG_LEVEL``, else ``INFO``.
    Safe to call more than once — sinks are replaced each time.
    """
    resolved = (level or os.environ.get("CSG_LOG_LEVEL") or "INFO").upper()
    logger.remove()
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
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
