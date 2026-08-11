"""Shared dependencies: templates and the local-token guard."""

from __future__ import annotations

from pathlib import Path

from fastapi import Cookie, Header, HTTPException, Query
from fastapi.templating import Jinja2Templates

from ..config import get_settings

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))

TOKEN_COOKIE = "csg_token"


def guard_path(raw) -> Path:
    """Resolve a client-supplied path, or refuse it with a 400 (#120).

    Checks the *resolved* location rather than the text, so a slug, a relative
    path and an absolute one are all judged by where they actually land.
    """
    from ..core import paths as core_paths

    try:
        return core_paths.resolve_input(raw)
    except core_paths.PathNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def require_token(
    x_csg_token: str | None = Header(default=None),
    token_q: str | None = Query(default=None, alias="token"),
    csg_token: str | None = Cookie(default=None),
) -> None:
    """Guard API routes. The index page plants the token as a cookie; the
    frontend also echoes it in a header. SSE (EventSource) relies on the cookie
    or a ``?token=`` query param.
    """
    expected = get_settings().token
    supplied = x_csg_token or token_q or csg_token
    if supplied != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
