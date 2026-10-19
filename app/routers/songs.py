"""歌曲档案：上传完整歌曲，转码保存，供后续分离与转换。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..audio import AUDIO_EXTS, AudioError, probe, transcode
from ..config import settings
from ..storage import list_items, new_id, now_iso, read_json, remove_dir, song_dir, write_json

router = APIRouter(prefix="/api/songs", tags=["songs"])


@router.get("")
def list_songs() -> list[dict]:
    return list_items(settings.songs_dir)


@router.post("")
async def create_song(
    title: str = Form("", max_length=120),
    artist: str = Form("", max_length=120),
    file: UploadFile = File(...),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in AUDIO_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix or '未知'}")

    song_id = new_id("song")
    root = song_dir(song_id)
    root.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    raw = root / "original" / f"upload{suffix}"
    raw.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with raw.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="文件超过大小限制")
                fh.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="空文件")

        wav = root / "source.wav"
        await asyncio.to_thread(transcode, raw, wav, sample_rate=44100, channels=2)
        info = await asyncio.to_thread(probe, wav)
    except HTTPException:
        remove_dir(root)
        raise
    except AudioError as exc:
        remove_dir(root)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        remove_dir(root)
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc
    finally:
        await file.close()

    meta = {
        "id": song_id,
        "title": title.strip() or Path(file.filename or "未命名").stem,
        "artist": artist.strip(),
        "created_at": now_iso(),
        "duration": round(info["duration"], 2),
        "sample_rate": info["sample_rate"],
        "filename": file.filename,
    }
    write_json(root / "meta.json", meta)
    return meta


@router.get("/{song_id}")
def get_song(song_id: str) -> dict:
    meta = read_json(song_dir(song_id) / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="歌曲不存在")
    return meta


@router.delete("/{song_id}")
def delete_song(song_id: str) -> dict:
    root = song_dir(song_id)
    if not (root / "meta.json").exists():
        raise HTTPException(status_code=404, detail="歌曲不存在")
    remove_dir(root)
    return {"ok": True}
