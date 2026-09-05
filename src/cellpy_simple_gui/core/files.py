"""Path/glob expansion for the file-loading inputs.

Turns a list of user-typed entries (literal paths and/or glob patterns like
``C:\\data\\*si*.h5``) into a concrete, de-duplicated file list, capped at a
limit, with human-readable messages for the "nothing matched" / "too many"
cases so the UI can tell the user what happened.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..config import DEFAULT_MAX_FILES, get_settings  # noqa: F401 - re-exported
from . import paths as _paths

_GLOB_CHARS = ("*", "?", "[")


def effective_max_files(requested: int | None) -> int:
    """Clamp a client-supplied cap to the policy for this session (#97).

    The UI reads the ceiling from ``/system/capabilities``, but the cap is
    enforced here so a stale or hand-made request cannot exceed it.
    """
    ceiling = get_settings().max_files
    if not requested or requested <= 0:
        return min(DEFAULT_MAX_FILES, ceiling)
    return min(requested, ceiling)


@dataclass
class Expansion:
    paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # nothing matched / not found
    notes: list[str] = field(default_factory=list)  # informational (e.g. truncation)


def is_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in _GLOB_CHARS)


def expand_paths(patterns: list[str], max_files: int = DEFAULT_MAX_FILES) -> Expansion:
    exp = Expansion()
    seen: set[str] = set()

    for raw in patterns:
        pat = raw.strip().strip('"')
        if not pat:
            continue
        # Remote SSH/SFTP URIs (#160): never run through local glob / resolve.
        # Desktop only; single-file URI in this phase (filefinder find = later).
        if _paths.is_remote_uri(pat):
            if not _paths.remote_paths_allowed():
                exp.errors.append(
                    f"Remote path refused: {pat}. This instance is served over "
                    "a network, so it only reads inside its own data directory "
                    "(SSH/SFTP remotes are desktop-only)."
                )
                continue
            if is_glob(pat):
                exp.errors.append(
                    f"Remote globs are not supported yet: {pat}. "
                    "Paste a single file URI (e.g. sftp://user@host/path/file.res)."
                )
                continue
            if pat not in seen:
                seen.add(pat)
                exp.paths.append(pat)
            continue
        # Both branches go through core.paths, so a served instance can only
        # ever reach inside its data directory (#120). On a desktop instance
        # these are pass-throughs.
        if is_glob(pat):
            hits = _paths.expand_glob(pat)
            if not hits:
                exp.errors.append(f"No files matched: {pat}")
                continue
            for h in hits:
                if h not in seen:
                    seen.add(h)
                    exp.paths.append(h)
        else:
            try:
                resolved = str(_paths.resolve_input(pat))
            except _paths.PathNotAllowed as exc:
                exp.errors.append(str(exc))
                continue
            if os.path.isfile(resolved):
                if resolved not in seen:
                    seen.add(resolved)
                    exp.paths.append(resolved)
            else:
                exp.errors.append(f"Not found: {pat}")

    limit = max_files if max_files and max_files > 0 else DEFAULT_MAX_FILES
    if len(exp.paths) > limit:
        exp.notes.append(
            f"Matched {len(exp.paths)} files; loaded the first {limit} "
            f"(raise “max” to load more)."
        )
        exp.paths = exp.paths[:limit]

    return exp
