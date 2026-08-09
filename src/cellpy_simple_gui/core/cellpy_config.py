"""Read-only view of cellpy's layered configuration.

Answers "where is cellpy reading this from?" — the question behind most
"why did my file end up *there*?" reports. cellpy ≥2.1.2 resolves settings in
layers (defaults → user ``cellpy.toml`` → project ``cellpy.toml`` → env → runtime)
and can name the winning layer per key via :func:`cellpy.config.sources`; this
module reshapes that into something the API and UI can render.

Read-only by design: the app does not write cellpy's user config (that file is
shared with the user's notebooks and CLI). Secret values are never surfaced —
the ``secrets`` section is skipped entirely and credential-ish instrument keys
are masked, because a legacy ``SQL_PWD`` can still ride along in the live config
(cellpy #849). The result is safe to render and safe to paste into a bug report.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Sections rendered expanded first — the ones support questions are about.
PRIMARY_SECTIONS = ("paths", "units")

#: Skipped entirely: credentials must never reach the UI.
_SKIP_SECTIONS = ("secrets",)

#: Value masked when the key looks like a credential (see cellpy #849).
_SECRET_KEY_HINTS = ("pwd", "password", "passwd", "secret", "token", "uid")

_MASK = "••••••"

#: Env vars cellpy reads credentials from; reported as present/absent only.
_SECRET_ENV_VARS = (
    "CELLPY_PASSWORD",
    "CELLPY_KEY_FILENAME",
    "CELLPY_HOST",
    "CELLPY_USER",
)


def _is_secretish(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in _SECRET_KEY_HINTS)


def _looks_like_path(section: str, key: str) -> bool:
    if section == "paths":
        return not key.endswith("filename")
    return key.endswith(("dir", "_file", "path"))


def _flatten(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested config dicts to ``[(dotted_key, value), ...]``."""
    out: list[tuple[str, Any]] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.extend(_flatten(value, path))
        else:
            out.append((path, value))
    return out


def _entry(section: str, dotted: str, value: Any, layer: str | None) -> dict:
    """One rendered setting: value (masked if secret-ish) + provenance layer."""
    leaf = dotted.rsplit(".", 1)[-1]
    secret = _is_secretish(leaf)
    is_path = not secret and _looks_like_path(section, leaf)
    text = _MASK if secret else ("" if value is None else str(value))
    entry = {
        "key": dotted,
        "label": dotted.split(".", 1)[1] if "." in dotted else dotted,
        "value": text,
        "layer": layer or "default",
        "secret": secret,
        "is_path": is_path,
    }
    if is_path and text:
        try:
            entry["exists"] = Path(text).exists()
        except (OSError, ValueError):  # noqa: BLE001 - odd paths stay renderable
            entry["exists"] = None
    return entry


def _sources() -> dict[str, str]:
    from cellpy import config

    try:
        return config.sources()
    except Exception:  # noqa: BLE001 - diagnostics must not be the thing that breaks
        log.warning("could not read cellpy config provenance", exc_info=True)
        return {}


def _config_dump() -> dict[str, Any]:
    from cellpy import config

    cfg = config.get_config()
    # mode="json" keeps Paths/OtherPaths as strings so this stays serializable.
    return cfg.model_dump(mode="json")


def _discovery() -> dict[str, Any]:
    """Which files cellpy looked for, and which it found."""
    from cellpy.config.loader import find_project_config_file, user_config_path

    info: dict[str, Any] = {}
    user_file = user_config_path()
    info["user_config_path"] = str(user_file)
    info["user_config_exists"] = user_file.is_file()

    project_file = None
    try:
        project_file = find_project_config_file()
    except Exception:  # noqa: BLE001
        log.warning("project cellpy.toml lookup failed", exc_info=True)
    info["project_config_path"] = str(project_file) if project_file else None

    legacy_file = None
    if not info["user_config_exists"]:
        try:
            from cellpy.config.legacy import find_legacy_yaml_file

            legacy_file = find_legacy_yaml_file()
        except Exception:  # noqa: BLE001
            log.warning("legacy config lookup failed", exc_info=True)
    info["legacy_config_path"] = str(legacy_file) if legacy_file else None
    # A legacy YAML only feeds the user layer when no cellpy.toml exists.
    info["legacy_fallback"] = bool(legacy_file) and not info["user_config_exists"]
    return info


def _secret_env_state() -> list[dict]:
    """Presence (never value) of the credential env vars cellpy reads."""
    import os

    return [
        {"name": name, "set": bool(os.environ.get(name))} for name in _SECRET_ENV_VARS
    ]


def _warnings(discovery: dict[str, Any], layer_counts: dict[str, int]) -> list[str]:
    out: list[str] = []
    if discovery["legacy_fallback"]:
        out.append(
            "cellpy is reading a legacy YAML config "
            f"({discovery['legacy_config_path']}) because no cellpy.toml exists yet. "
            "Migrating to cellpy.toml is recommended — the legacy format is a "
            "compatibility fallback."
        )
    elif not discovery["user_config_exists"] and not layer_counts.get("user_file"):
        out.append(
            "No user cellpy.toml found — cellpy is running on built-in defaults, "
            f"so data is read from and written under {Path.home()}."
        )
    if discovery["project_config_path"]:
        out.append(
            "A project cellpy.toml was found next to the working directory "
            f"({discovery['project_config_path']}); its settings override your user config."
        )
    return out


def diagnostics() -> dict:
    """Everything the config panel renders. Never raises, never leaks secrets."""
    import cellpy

    dump = _config_dump()
    provenance = _sources()
    discovery = _discovery()

    sections: list[dict] = []
    layer_counts: dict[str, int] = {}
    for name, payload in dump.items():
        if name in _SKIP_SECTIONS or not isinstance(payload, dict):
            continue
        entries = [
            _entry(name, dotted, value, provenance.get(dotted))
            for dotted, value in _flatten(payload, name)
        ]
        for item in entries:
            layer_counts[item["layer"]] = layer_counts.get(item["layer"], 0) + 1
        sections.append(
            {
                "name": name,
                "primary": name in PRIMARY_SECTIONS,
                "entries": sorted(entries, key=lambda e: e["key"]),
            }
        )
    sections.sort(key=lambda s: (not s["primary"], s["name"]))

    return {
        "cellpy_version": getattr(cellpy, "__version__", "unknown"),
        "discovery": discovery,
        "sections": sections,
        "layer_counts": layer_counts,
        "secret_env": _secret_env_state(),
        "warnings": _warnings(discovery, layer_counts),
    }
