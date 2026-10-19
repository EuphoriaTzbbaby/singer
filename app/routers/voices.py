"""音色档案：上传训练素材、查看、删除。

当前版本只负责收素材和转码；RVC 模型训练与导入在后续里程碑接入。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..audio import AUDIO_EXTS, AudioError, probe, transcode
from ..config import settings
from ..storage import (
    list_items,
    new_id,
    now_iso,
    read_json,
    remove_dir,
    voice_dir,
    write_json,
)

router = APIRouter(prefix="/api/voices", tags=["voices"])

MIN_TRAIN_SECONDS = 60
RECOMMENDED_SECONDS = 600


async def _save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with dest.open("wb") as fh:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="文件超过大小限制")
                fh.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="空文件")
    return size


@router.get("")
def list_voices() -> list[dict]:
    return list_items(settings.voices_dir)


@router.post("")
async def create_voice(
    name: str = Form(..., min_length=1, max_length=60),
    consent: bool = Form(False),
    files: list[UploadFile] = File(...),
) -> dict:
    if not consent:
        raise HTTPException(status_code=400, detail="必须确认声音为本人所有或已获授权")

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个音频文件")

    voice_id = new_id("voice")
    root = voice_dir(voice_id)
    originals = root / "dataset" / "original"
    wavs = root / "dataset" / "wav"
    originals.mkdir(parents=True, exist_ok=True)
    wavs.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    saved: list[dict] = []
    total_duration = 0.0
    try:
        for index, upload in enumerate(files, start=1):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in AUDIO_EXTS:
                raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix or '未知'}")
            raw = originals / f"{index:03d}{suffix}"
            await _save_upload(upload, raw, max_bytes)
            wav = wavs / f"{index:03d}.wav"
            try:
                await asyncio.to_thread(transcode, raw, wav, sample_rate=44100, channels=1)
                info = await asyncio.to_thread(probe, wav)
            except AudioError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            total_duration += info["duration"]
            saved.append(
                {
                    "name": upload.filename,
                    "file": str(wav.relative_to(root)),
                    "duration": round(info["duration"], 2),
                }
            )
    except HTTPException:
        remove_dir(root)
        raise
    except Exception as exc:  # noqa: BLE001
        remove_dir(root)
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc

    warnings: list[str] = []
    if total_duration < MIN_TRAIN_SECONDS:
        warnings.append("素材不足 1 分钟，无法训练；建议至少 10 分钟干净人声。")
    elif total_duration < RECOMMENDED_SECONDS:
        warnings.append("素材少于 10 分钟，可以训练但相似度可能有限。")

    meta = {
        "id": voice_id,
        "name": name.strip(),
        "created_at": now_iso(),
        "consent_at": now_iso(),
        "kind": "rvc_dataset",
        "files": saved,
        "total_duration": round(total_duration, 2),
        "has_model": False,
        "model": None,
    }
    write_json(root / "meta.json", meta)
    return {**meta, "warnings": warnings}


@router.get("/{voice_id}")
def get_voice(voice_id: str) -> dict:
    root = voice_dir(voice_id)
    meta = read_json(root / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="音色不存在")
    return meta


@router.delete("/{voice_id}")
def delete_voice(voice_id: str) -> dict:
    root = voice_dir(voice_id)
    if not (root / "meta.json").exists():
        raise HTTPException(status_code=404, detail="音色不存在")
    remove_dir(root)
    return {"ok": True}
