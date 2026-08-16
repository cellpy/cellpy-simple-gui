"""Files brought in through the browser (#133).

A served instance may only read inside ``CSG_DATA_DIR`` (#120). That boundary is
right, but it leaves someone using the app through a browser on another machine
with no way to bring in a file at all — "paste a path" describes a filesystem
they cannot see. Uploads are the way in, and they land *inside* the boundary
rather than around it.

Nothing here trusts the client. The filename is used for its stem only, the
destination is re-checked against the sandbox after resolution, and the size cap
is enforced while streaming rather than after — a cap you apply once the file is
already on disk is not a cap.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ..config import get_settings
from . import paths as _paths

log = logging.getLogger(__name__)

#: Anything outside this is replaced. Deliberately strict rather than clever:
#: these names are only ever used to build a path we control.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

#: Read size. Big enough not to be silly for a 200 MB cellpy file, small enough
#: that the cap is enforced long before memory is a problem.
_CHUNK = 1024 * 1024


class UploadRejected(ValueError):
    """The upload cannot be accepted — bad name, too large, nowhere to put it."""


@dataclass
class Saved:
    path: Path
    size: int


def uploads_dir() -> Path:
    """Where uploads live: ``<data_dir>/uploads``.

    Inside the sandbox on purpose, so an uploaded file is reachable by exactly
    the same rules as anything else the instance may read.
    """
    return get_settings().data_dir / "uploads"


def safe_name(raw: str | None) -> str:
    """A filename we are willing to create.

    Only the final component is considered, so ``../../etc/passwd`` and
    ``C:\\Windows\\evil.dll`` both reduce to their last segment before anything
    else happens. The result is then reduced to a conservative character set.
    """
    candidate = (raw or "").strip().replace("\\", "/")
    candidate = candidate.rsplit("/", 1)[-1]
    candidate = _UNSAFE.sub("_", candidate).strip("._")
    if not candidate:
        raise UploadRejected("That file has no usable name.")
    return candidate[:120]


def _unique(directory: Path, name: str) -> Path:
    """Never silently overwrite: two uploads of `cell.h5` are two files."""
    target = directory / name
    if not target.exists():
        return target
    stem, dot, suffix = name.partition(".")
    for n in range(1, 1000):
        candidate = directory / f"{stem}-{n}{dot}{suffix}"
        if not candidate.exists():
            return candidate
    raise UploadRejected(f"Too many files named like {name!r}.")


def max_upload_bytes() -> int:
    return get_settings().max_upload_mb * 1024 * 1024


def save(stream: BinaryIO, filename: str | None) -> Saved:
    """Stream one upload to disk, refusing it if it grows past the cap."""
    directory = uploads_dir()
    directory.mkdir(parents=True, exist_ok=True)

    target = _unique(directory, safe_name(filename))

    # Belt and braces: the name is already sanitised, but the destination is
    # checked the same way any client-supplied path would be. If this ever
    # fails, the sanitiser has a hole and this is the thing that catches it.
    resolved = target.resolve()
    root = _paths.sandbox_root() or get_settings().data_dir
    if not (resolved == root or resolved.is_relative_to(root.resolve())):
        raise UploadRejected("Refusing to write outside the data directory.")

    cap = max_upload_bytes()
    written = 0
    try:
        with open(target, "wb") as fh:
            while chunk := stream.read(_CHUNK):
                written += len(chunk)
                if written > cap:
                    raise UploadRejected(
                        f"{target.name} is larger than the {get_settings().max_upload_mb} MB "
                        "upload limit (CSG_MAX_UPLOAD_MB)."
                    )
                fh.write(chunk)
    except Exception:
        # A partial file would look like a real one to the loader.
        target.unlink(missing_ok=True)
        raise

    if written == 0:
        target.unlink(missing_ok=True)
        raise UploadRejected(f"{target.name} is empty.")

    log.info("Uploaded %s (%d bytes)", target.name, written)
    return Saved(path=target, size=written)


def usage() -> dict:
    """What is sitting in the uploads folder, so it is not a mystery."""
    directory = uploads_dir()
    if not directory.is_dir():
        return {"files": 0, "bytes": 0}
    files = [f for f in directory.rglob("*") if f.is_file()]
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}


def clear() -> dict:
    """Delete every uploaded file.

    Uploads are never pruned automatically. Between uploading and saving a
    project there is a window where the file is the only copy, and silently
    deleting somebody's data to reclaim disk is a worse failure than letting a
    folder grow — so this is a button, not a timer.
    """
    directory = uploads_dir()
    removed = freed = 0
    if directory.is_dir():
        for f in sorted(directory.rglob("*"), key=lambda p: -len(p.parts)):
            if f.is_file():
                freed += f.stat().st_size
                f.unlink(missing_ok=True)
                removed += 1
    log.info("Cleared %d upload(s), %d bytes", removed, freed)
    return {"removed": removed, "bytes": freed}
