"""Path/glob expansion for the file-loading inputs.

Turns a list of user-typed entries (literal paths and/or glob patterns like
``C:\\data\\*si*.h5``) into a concrete, de-duplicated file list, capped at a
limit, with human-readable messages for the "nothing matched" / "too many"
cases so the UI can tell the user what happened.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

_GLOB_CHARS = ("*", "?", "[")

DEFAULT_MAX_FILES = 10


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
        if is_glob(pat):
            hits = sorted(p for p in glob.glob(pat, recursive=True) if os.path.isfile(p))
            if not hits:
                exp.errors.append(f"No files matched: {pat}")
                continue
            for h in hits:
                if h not in seen:
                    seen.add(h)
                    exp.paths.append(h)
        else:
            if os.path.isfile(pat):
                if pat not in seen:
                    seen.add(pat)
                    exp.paths.append(pat)
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
