"""FastAPI 入口：静态页面 + JSON API。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import settings
from .routers import recordings, songs, voices

logger = logging.getLogger("uvicorn.error")

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
REMOTE_PUBLIC_PATHS = {
    "/record",
    "/api/recordings",
    "/static/style.css",
    "/static/record.css",
    "/static/record.js",
    "/favicon.ico",
}


class RemoteAccessGuard(BaseHTTPMiddleware):
    """通过隧道访问时，只开放录音页与其静态资源。"""

    async def dispatch(self, request, call_next):
        if settings.allow_remote_admin:
            return await call_next(request)
        host = request.url.hostname or ""
        if host in LOCAL_HOSTS:
            return await call_next(request)
        if request.url.path in REMOTE_PUBLIC_PATHS:
            return await call_next(request)
        return JSONResponse(
            {"detail": "远程访问只开放录音页；管理界面请在本机打开"},
            status_code=403,
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    token = settings.ensure_record_token()
    logger.info("录音页: http://127.0.0.1:%s/record?token=%s", settings.port, token)
    yield


app = FastAPI(title="Singer", version="0.1.0", lifespan=lifespan)
app.add_middleware(RemoteAccessGuard)

app.include_router(voices.router)
app.include_router(songs.router)
app.include_router(recordings.router)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": app.version,
        "data_dir": str(settings.data_dir),
        "voice_count": len(list(settings.voices_dir.glob("*/meta.json"))),
        "song_count": len(list(settings.songs_dir.glob("*/meta.json"))),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")
