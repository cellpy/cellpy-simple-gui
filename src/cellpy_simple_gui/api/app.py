"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..core import cellpy_adapter
from .deps import TEMPLATES, TOKEN_COOKIE, WEB_DIR, require_token
from .routers import cells, export, ingest, jobs, plots, projects, system

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
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
