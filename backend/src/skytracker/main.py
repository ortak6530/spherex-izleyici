"""FastAPI application: API under /api/v1, WebSocket at /ws, built frontend (SPA) at /."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.v1 import router as api_router
from .config_loader import attributions, demo_targets, releases, upstreams
from .db import session_scope
from .events import purge_old
from .realtime import router as ws_router
from .security import SecurityHeadersMiddleware, SessionMiddleware
from .settings import get_settings

log = logging.getLogger("skytracker")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    # Fail fast on broken configuration rather than at the first request
    releases(), upstreams(), demo_targets(), attributions()
    if s.is_production and (not s.secret_key or not s.ip_hash_salt):
        log.warning("SECRET_KEY / IP_HASH_SALT are not set; set them in the Render dashboard")
    try:
        with session_scope() as db:
            n = purge_old(db, s.event_retention_days)
            if n:
                log.info("purged %d events older than %d days", n, s.event_retention_days)
    except Exception:  # noqa: BLE001 - DB may not be migrated yet in a fresh dev checkout
        log.exception("event retention purge failed (did you run 'alembic upgrade head'?)")
    yield
    from .http import http

    await http.aclose()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="SPHEREx Gökyüzü İzleyici API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if s.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if s.is_production else "/api/openapi.json",
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SessionMiddleware)
    if not s.is_production and s.origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=s.origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )

    @app.exception_handler(HTTPException)
    async def _http(_req: Request, exc: HTTPException):
        # Error contract: {"code": ..., ...}; the frontend turns codes into Turkish text
        body = exc.detail if isinstance(exc.detail, dict) else {"code": f"HTTP_{exc.status_code}"}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"code": "INVALID_INPUT"})

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR"})

    app.include_router(api_router)
    app.include_router(ws_router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    dist = get_settings().frontend_dist
    index = dist / "index.html"
    if not index.exists():
        log.warning("frontend build not found at %s (run 'npm run build' in frontend/)", dist)
        return
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith(("api/", "ws")):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        # Serve real top-level files (favicon, robots.txt…) but never escape the dist folder
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
