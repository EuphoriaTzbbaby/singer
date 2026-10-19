"""FastAPI 入口：静态页面 + JSON API。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import songs, voices


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="Singer", version="0.1.0", lifespan=lifespan)

app.include_router(voices.router)
app.include_router(songs.router)
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
