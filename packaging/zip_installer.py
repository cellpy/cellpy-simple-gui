"""Zip each Windows installer ``.exe`` beside itself (#173).

A corporate download filter often refuses ``.exe`` and allows ``.zip``. The
archive contains that same installer, at the root, under its own file name.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def zip_installers(directory: Path) -> list[Path]:
    """Write ``<name>.zip`` next to every ``*.exe`` in ``directory``.

    Args:
        directory: Folder that already holds the installer executable(s).

    Returns:
        The zip paths, one per installer, in sorted name order.

    Raises:
        SystemExit: When ``directory`` contains no ``.exe``.
    """
    folder = Path(directory)
    exes = sorted(p for p in folder.glob("*.exe") if p.is_file())
    if not exes:
        raise SystemExit(f"no installer exe in {folder}")
    written: list[Path] = []
    for exe in exes:
        dest = exe.with_suffix(".zip")
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(exe, exe.name)
        written.append(dest)
    return written


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("usage: zip_installer.py <directory>")
    for path in zip_installers(Path(args[0])):
        print(path)


if __name__ == "__main__":
    main()
