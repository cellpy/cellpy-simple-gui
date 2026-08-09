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
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: A project may carry its own cellpy settings next to ``project.json``.
PROJECT_CONFIG_FILENAME = "cellpy.toml"

# Activating a project config swaps cellpy's *process-global* session, so it is
# serialised here and must only be driven from the request thread — never from a
# job worker (cellpy #850: the config session is not thread-safe).
_config_lock = threading.RLock()
_active_project_config: Path | None = None

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


# --------------------------------------------------------------------------- #
# Per-project cellpy settings
# --------------------------------------------------------------------------- #


def project_config_path(project_dir: str | Path) -> Path:
    """Where a project's own cellpy settings live."""
    return Path(project_dir) / PROJECT_CONFIG_FILENAME


#: Sections written when pinning settings to a project.
#:
#: Deliberately *not* ``paths`` — a project is portable, and baking this
#: machine's directory layout into it would break it on someone else's box.
#: Deliberately not ``instruments``/``db`` either: those carry connection
#: details, and this way the written file structurally cannot contain a
#: credential, independently of cellpy's own dump scrubbing (#849/#857).
PINNED_SECTIONS = ("reader", "units", "defaults")


def active_project_config() -> Path | None:
    """The project ``cellpy.toml`` this app activated, if any."""
    with _config_lock:
        return _active_project_config


def pin_project_config(project_dir: str | Path) -> Path:
    """Write the settings that shape *interpretation* into the project, and activate it.

    Captures the resolved ``reader`` / ``units`` / ``defaults`` in full — not
    just what differs from today's defaults — so the project keeps reproducing
    the same numbers even if cellpy's defaults move later.

    Returns the written path. Overwrites any existing project config.
    """
    from cellpy import config
    from cellpy.config.loader import write_toml

    # model_dump_for_file() already drops `secrets`; the section allow-list below
    # is the structural guarantee (belt and braces — see PINNED_SECTIONS).
    dump = config.get_config().model_dump_for_file()
    payload = {name: dump[name] for name in PINNED_SECTIONS if name in dump}
    if not payload:
        raise RuntimeError("cellpy reported no settings to pin.")

    path = project_config_path(project_dir)
    write_toml(path, payload)
    log.info("Pinned cellpy settings to %s (%s)", path, ", ".join(payload))
    activate_project_config(project_dir)
    return path


def activate_project_config(project_dir: str | Path) -> Path | None:
    """Make ``<project>/cellpy.toml`` cellpy's project layer.

    A project can pin the settings its data was analysed with — ``reader``
    (cycle mode, interpolation), ``units``, ``defaults`` — so reopening it later
    reproduces the same numbers instead of silently re-interpreting the data
    under whatever the user's global config happens to say now.

    Returns the activated path, or ``None`` when the project has no config (in
    which case any previously active one is dropped, so projects never leak
    settings into each other).

    Call from the request thread *before* loading cells, so the load happens
    under the project's settings — and never from a job worker (cellpy #850).
    """
    global _active_project_config

    path = project_config_path(project_dir)
    with _config_lock:
        if not path.is_file():
            if _active_project_config is not None:
                log.info("Project has no %s — reverting to user config", PROJECT_CONFIG_FILENAME)
            _deactivate_locked()
            return None
        try:
            from cellpy import config
            from cellpy.config.loader import LoadOptions

            config.set_load_options(LoadOptions(project_config_file=path))
            config.reload()
        except Exception:  # noqa: BLE001 - a bad project config must not block opening
            log.warning("Could not activate project config %s", path, exc_info=True)
            _deactivate_locked()
            return None
        _active_project_config = path
        log.info("Activated project cellpy config: %s", path)
        return path


def deactivate_project_config() -> None:
    """Drop any project layer — back to user config + environment."""
    with _config_lock:
        _deactivate_locked()


def _deactivate_locked() -> None:
    global _active_project_config

    if _active_project_config is None:
        return
    try:
        from cellpy import config

        config.set_load_options(None)
        config.reload()
    except Exception:  # noqa: BLE001
        log.warning("Could not restore the user cellpy config", exc_info=True)
    finally:
        _active_project_config = None


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
    """Which config files actually apply, straight from cellpy.

    ``active_config_file`` (cellpy #851/#853) is the loader's own answer, so this
    panel and ``load_config`` cannot disagree about which file wins — including
    a legacy ``.conf`` that still exists but is outranked by a ``cellpy.toml``.
    """
    from cellpy.config.loader import LoadOptions, active_config_file, user_config_path

    active = active_project_config()
    try:
        resolved = active_config_file(
            LoadOptions(project_config_file=active) if active else None
        )
    except Exception:  # noqa: BLE001 - diagnostics must never be the thing that breaks
        log.warning("could not resolve the active cellpy config file", exc_info=True)
        return {
            "user_config_path": str(user_config_path()),
            "user_config_exists": False,
            "user_config_kind": "unknown",
            "shadowed_legacy": None,
            "project_config_path": None,
            "project_config_source": None,
            "legacy_config_path": None,
            "legacy_fallback": False,
        }

    return {
        # The file that actually feeds the user layer (or where one would live).
        "user_config_path": str(resolved.path or user_config_path()),
        "user_config_exists": resolved.kind != "none",
        "user_config_kind": resolved.kind,  # "toml" | "legacy" | "none"
        # A legacy .conf that still exists but lost to a cellpy.toml.
        "shadowed_legacy": str(resolved.shadowed_legacy) if resolved.shadowed_legacy else None,
        "project_config_path": str(resolved.project_path) if resolved.project_path else None,
        "project_config_source": (
            "project" if active and resolved.project_path else
            ("discovered" if resolved.project_path else None)
        ),
        "legacy_config_path": str(resolved.path) if resolved.kind == "legacy" else None,
        "legacy_fallback": resolved.kind == "legacy",
    }


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
    if discovery.get("shadowed_legacy"):
        out.append(
            f"A legacy config ({discovery['shadowed_legacy']}) still exists but is "
            "ignored — your cellpy.toml outranks it. Edits to the old file have no "
            "effect; delete it once you are happy with the migration."
        )
    if discovery.get("project_config_source") == "project":
        out.append(
            "This project carries its own cellpy settings "
            f"({discovery['project_config_path']}); they override your user config "
            "while the project is open."
        )
    elif discovery["project_config_path"]:
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
