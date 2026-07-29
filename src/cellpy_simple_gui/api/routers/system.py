"""System endpoints: capability probe + native file pickers (desktop only)."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

router = APIRouter()

_FILE_TYPES = {
    "cellpy": ("Cellpy files (*.cellpy;*.h5)", "All files (*.*)"),
    "raw": ("All files (*.*)",),
    "journal": ("Journal files (*.json)", "All files (*.*)"),
}


def _webview_window():
    """The active pywebview window, or None when running as a plain server."""
    try:
        import webview

        return webview.windows[0] if getattr(webview, "windows", None) else None
    except Exception:  # noqa: BLE001
        return None


@router.get("/system/capabilities")
def capabilities() -> dict:
    return {"file_picker": _webview_window() is not None}


@router.post("/system/pick")
def pick(kind: str = Body("cellpy", embed=True)) -> dict:
    """Open a native file-open dialog and return the chosen absolute paths."""
    win = _webview_window()
    if win is None:
        raise HTTPException(400, "The file picker is only available in the desktop app.")
    import webview

    file_types = _FILE_TYPES.get(kind, ("All files (*.*)",))
    result = win.create_file_dialog(
        webview.FileDialog.OPEN,
        allow_multiple=(kind != "journal"),
        file_types=file_types,
    )
    return {"paths": [str(p) for p in result] if result else []}
