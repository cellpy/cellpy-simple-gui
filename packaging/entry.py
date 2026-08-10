"""Frozen-app entry point.

A module of its own rather than pointing PyInstaller at ``__main__.py``: the
frozen process has no ``-m`` semantics, and multiprocessing needs the freeze
support call before anything else touches threads.
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    # Without this, a frozen child process re-runs the whole app instead of the
    # worker function. polars/pyarrow may spawn; cheap insurance either way.
    multiprocessing.freeze_support()
    from cellpy_simple_gui.__main__ import main as app_main

    return app_main() or 0


if __name__ == "__main__":
    sys.exit(main())
