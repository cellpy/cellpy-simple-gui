"""System endpoints: capability probe, native file pickers, config diagnostics."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ...config import get_settings
from ...core import cellpy_config
from ...logging_setup import recent_logs, ring_enabled
from ..jobs import get_job_manager
from .plots import require_dev_mode

log = logging.getLogger(__name__)
router = APIRouter()

_FILE_TYPES = {
    "cellpy": ("Cellpy files (*.cellpy;*.h5)", "All files (*.*)"),
    "raw": ("All files (*.*)",),
    # pywebview parse_file_type only allows [\\w ] in the description (no / or .).
    "journal": ("JSON files (*.json)", "All files (*.*)"),
}

_SAVE_TYPE_BY_EXT = {
    "csv": "CSV (*.csv)",
    "xlsx": "Excel (*.xlsx)",
    "parquet": "Parquet (*.parquet)",
    "json": "JSON (*.json)",
    "png": "PNG (*.png)",
    "svg": "SVG (*.svg)",
    "pdf": "PDF (*.pdf)",
    "cellpy": "Cellpy (*.cellpy)",
    "zip": "ZIP archive (*.zip)",
}


def _webview_window():
    """The active pywebview window, or None when running as a plain server."""
    try:
        import webview

        return webview.windows[0] if getattr(webview, "windows", None) else None
    except Exception:  # noqa: BLE001
        return None


def _save_file_types(filename: str) -> tuple[str, ...]:
    ext = Path(filename).suffix.lower().lstrip(".")
    specific = _SAVE_TYPE_BY_EXT.get(ext)
    if specific:
        return (specific, "All files (*.*)")
    return ("All files (*.*)",)


def _normalize_dialog_path(result) -> str | None:
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        return str(result[0]) if result else None
    return str(result)


@router.get("/system/capabilities")
def capabilities() -> dict:
    settings = get_settings()
    from ...core import paths as core_paths

    return {
        "file_picker": _webview_window() is not None,
        "dev_mode": settings.dev_mode,
        "max_files": settings.max_files,
        # Upload is how a browser on another machine gets a file in at all
        # (#133); the UI leans on it when host paths are refused.
        "max_upload_mb": settings.max_upload_mb,
        # Whether typing a host path works here, and if not, what the boundary
        # is (#120) — so the UI can say so rather than looking broken.
        **core_paths.describe_mode(),
    }


@router.get("/system/logs")
def logs(limit: int = Query(300, ge=1, le=2000), level: str | None = None) -> dict:
    """Recent log records — developer mode (#97).

    Saves a round trip to ``cellpy_debug.log`` when a load fails: cellpy's own
    records arrive here too, through the stdlib bridge.
    """
    require_dev_mode()
    return {
        "records": recent_logs(limit=limit, level=level),
        "capturing": ring_enabled(),
    }


@router.get("/system/jobs")
def job_timings(limit: int = Query(25, ge=1, le=200)) -> dict:
    """Recent jobs with queue and run times — developer mode (#97)."""
    require_dev_mode()
    jobs = sorted(
        get_job_manager().all(), key=lambda j: j.created_at, reverse=True
    )[:limit]
    return {"jobs": [j.timing() for j in jobs]}


@router.get("/system/cellpy-config")
def cellpy_config_diagnostics() -> dict:
    """Where cellpy resolves each setting from (read-only; secrets never included)."""
    try:
        return cellpy_config.diagnostics()
    except Exception as exc:  # noqa: BLE001 - a broken probe must not break the app
        log.error("cellpy config diagnostics failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Could not read cellpy configuration: {exc}") from exc


@router.post("/system/pick")
def pick(kind: str = Body("cellpy", embed=True)) -> dict:
    """Open a native file-open (or folder) dialog and return chosen absolute paths."""
    win = _webview_window()
    if win is None:
        raise HTTPException(400, "The file picker is only available in the desktop app.")
    import webview

    if kind == "folder":
        result = win.create_file_dialog(webview.FileDialog.FOLDER)
        path = _normalize_dialog_path(result)
        return {"paths": [path] if path else []}

    file_types = _FILE_TYPES.get(kind, ("All files (*.*)",))
    result = win.create_file_dialog(
        webview.FileDialog.OPEN,
        allow_multiple=(kind != "journal"),
        file_types=file_types,
    )
    return {"paths": [str(p) for p in result] if result else []}


@router.post("/system/save")
async def save(
    request: Request,
    filename: str = Query(..., min_length=1, description="Suggested file name"),
) -> dict:
    """Show a native Save As dialog and write the request body to the chosen path.

    Used by desktop exports: the browser ``<a download>`` trick does not reliably
    land files in the user's Downloads folder under pywebview.
    """
    win = _webview_window()
    if win is None:
        raise HTTPException(400, "Save As is only available in the desktop app.")
    import webview

    suggested = Path(filename).name or "export.bin"
    data = await request.body()
    if not data:
        raise HTTPException(400, "Empty export payload.")

    result = win.create_file_dialog(
        webview.FileDialog.SAVE,
        save_filename=suggested,
        file_types=_save_file_types(suggested),
    )
    path = _normalize_dialog_path(result)
    if path is None:
        log.info("Save As cancelled (%s)", suggested)
        return {"path": None, "cancelled": True}

    dest = Path(path)
    try:
        dest.write_bytes(data)
    except OSError as exc:
        log.error("Save As write failed (%s): %s", dest, exc)
        raise HTTPException(500, f"Could not write file: {exc}") from exc
    log.info("Saved export to %s (%d bytes)", dest, len(data))
    return {"path": str(dest.resolve()), "cancelled": False}
