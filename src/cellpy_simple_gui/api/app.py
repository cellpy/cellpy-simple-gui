"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..core import cellpy_adapter
from ..logging_setup import enable_ring_buffer
from .deps import TEMPLATES, TOKEN_COOKIE, WEB_DIR, require_token
from .routers import cells, export, ingest, jobs, plots, projects, system, uploads

log = logging.getLogger(__name__)

#: Query-string stamp on our own static assets. The app version alone would not
#: change during development, so a dev-mode session also mixes in the file
#: mtimes and picks up edits on reload.
def _asset_version() -> str:
    from .. import __version__

    stamp = __version__
    try:
        newest = max(
            path.stat().st_mtime
            for name in ("static/js/app.js", "static/css/app.css")
            if (path := WEB_DIR / name).is_file()
        )
        stamp = f"{__version__}-{int(newest)}"
    except (OSError, ValueError):  # noqa: BLE001 - fall back to the version alone
        pass
    return stamp


_ASSET_VERSION = _asset_version()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.dev_mode:
        # Start capturing before any router runs, so the viewer has the startup
        # records too — including cellpy's, via the stdlib bridge (#97).
        enable_ring_buffer()
    app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None)

    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    # Protected API routers.
    guarded = [Depends(require_token)]
    app.include_router(cells.router, prefix="/api", dependencies=guarded)
    app.include_router(plots.router, prefix="/api", dependencies=guarded)
    app.include_router(export.router, prefix="/api", dependencies=guarded)
    app.include_router(jobs.router, prefix="/api", dependencies=guarded)
    app.include_router(projects.router, prefix="/api", dependencies=guarded)
    app.include_router(ingest.router, prefix="/api", dependencies=guarded)
    app.include_router(uploads.router, prefix="/api", dependencies=guarded)
    app.include_router(system.router, prefix="/api", dependencies=guarded)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        """Serve the single-page shell and plant the session token as a cookie."""
        try:
            version = cellpy_adapter.cellpy_version()
        except Exception:  # noqa: BLE001
            version = "?"
        response = TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "token": settings.token,
                "app_name": settings.app_name,
                "cellpy_version": version,
                # Cache-bust our own assets: without this a browser happily
                # keeps a stale app.js after an upgrade and runs it against the
                # new template and API.
                "asset_v": _ASSET_VERSION,
            },
        )
        response.set_cookie(
            TOKEN_COOKIE, settings.token, httponly=True, samesite="strict"
        )
        return response

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app
