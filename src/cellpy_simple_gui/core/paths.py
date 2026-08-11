"""Where the app is allowed to read and write (#120).

The desktop app takes host paths on purpose: typing ``D:\\data\\*.res`` is the
product. The moment the same app answers requests over a network, that same
freedom is arbitrary read and write on the *host*, gated only by a per-launch
token — and the blast radius is the machine, not the app.

So there are two modes:

**local** — bound to loopback. Anything the user can reach, as today.

**served** — bound to anything else. Paths resolve inside ``data_dir`` and
nothing may escape it.

The mode is inferred from the bind address and can be forced with
``CSG_ALLOW_HOST_PATHS``. Forcing it *off* matters for one real case: an
instance bound to loopback but published by a reverse proxy looks local to this
code, because the proxy connects from loopback.
"""

from __future__ import annotations

import glob as _glob
import logging
import os
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

#: Bind addresses that mean "only this machine can reach me".
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1"})


class PathNotAllowed(ValueError):
    """A supplied path resolves outside what this instance may touch."""


def host_paths_allowed() -> bool:
    """True when the app may read and write anywhere the user can."""
    settings = get_settings()
    override = getattr(settings, "allow_host_paths", None)
    if override is not None:
        return bool(override)
    return settings.host in LOOPBACK_HOSTS


def sandbox_root() -> Path | None:
    """The directory paths are confined to, or ``None`` when unconfined."""
    if host_paths_allowed():
        return None
    return get_settings().data_dir


def _contains(root: Path, candidate: Path) -> bool:
    try:
        return candidate == root or candidate.is_relative_to(root)
    except ValueError:  # different drives on Windows
        return False


def resolve_input(raw: str | os.PathLike[str]) -> Path:
    """Resolve a user-supplied path, refusing anything outside the sandbox.

    Resolution happens *before* the check, and follows symlinks, so ``..``
    segments and a link pointing out of the tree are both caught by the same
    comparison rather than by pattern-matching the string.
    """
    root = sandbox_root()
    text = str(raw).strip().strip('"')
    if not text:
        raise PathNotAllowed("No path given.")

    candidate = Path(text).expanduser()
    if root is None:
        return candidate

    # A relative path is relative to the sandbox, not to the process cwd —
    # which on a server is an implementation detail nobody typed.
    if not candidate.is_absolute():
        candidate = root / candidate

    resolved = candidate.resolve()
    if not _contains(root, resolved):
        log.warning("refused path outside %s: %s", root, text)
        raise PathNotAllowed(
            f"“{text}” is outside the data directory. This instance is served "
            "over a network, so it only reads and writes inside its own data "
            "directory."
        )
    return resolved


def expand_glob(pattern: str) -> list[str]:
    """Expand a glob, dropping anything that lands outside the sandbox.

    Filtering the *results* rather than validating the pattern is deliberate:
    ``**`` and symlinked directories can reach outside a prefix that looks
    perfectly innocent, and only the resolved hit tells the truth.
    """
    root = sandbox_root()
    text = pattern.strip().strip('"')
    if root is not None and not Path(text).expanduser().is_absolute():
        text = str(root / text)

    hits = [p for p in _glob.glob(text, recursive=True) if os.path.isfile(p)]
    if root is None:
        return sorted(hits)

    allowed: list[str] = []
    for hit in hits:
        resolved = Path(hit).resolve()
        if _contains(root, resolved):
            allowed.append(str(resolved))
        else:
            log.warning("glob hit outside %s dropped: %s", root, hit)
    return sorted(allowed)


def describe_mode() -> dict:
    """What the UI shows so a user knows which rules are in force."""
    root = sandbox_root()
    return {
        "host_paths_allowed": root is None,
        "sandbox_root": str(root) if root else None,
    }
