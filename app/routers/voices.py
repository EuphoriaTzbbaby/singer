"""音色档案：上传/追加训练素材、切片质检、训练包下载、RVC 模型导入。"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..audio import AUDIO_EXTS, AudioError, probe, transcode
from ..config import settings
from ..pipeline.dataset import prepare_training_pack
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

MIN_TRAIN_SECONDS = 300
RECOMMENDED_SECONDS = 600
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _root_for(voice_id: str) -> Path:
    if not ID_PATTERN.match(voice_id):
        raise HTTPException(status_code=404, detail="音色不存在")
    root = voice_dir(voice_id)
    if not (root / "meta.json").exists():
        raise HTTPException(status_code=404, detail="音色不存在")
    return root


def _warnings(total_duration: float) -> list[str]:
    if total_duration < MIN_TRAIN_SECONDS:
        return ["素材不足 5 分钟，训练效果会很有限；建议补到 10–15 分钟。"]
    if total_duration < RECOMMENDED_SECONDS:
        return ["素材少于 10 分钟，可以训练；10–15 分钟效果更稳。"]
    return []


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


def _next_index(wavs: Path) -> int:
    indices = [int(path.stem) for path in wavs.glob("*.wav") if path.stem.isdigit()]
    return max(indices, default=0) + 1


async def _store_files(
    root: Path, files: list[UploadFile], start_index: int
) -> tuple[list[dict], float]:
    """保存并转码一组素材；失败时清理本次已写入的文件。"""
    originals = root / "dataset" / "original"
    wavs = root / "dataset" / "wav"
    originals.mkdir(parents=True, exist_ok=True)
    wavs.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    saved: list[dict] = []
    added: list[Path] = []
    total_duration = 0.0
    try:
        for offset, upload in enumerate(files):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in AUDIO_EXTS:
                raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix or '未知'}")
            index = start_index + offset
            raw = originals / f"{index:03d}{suffix}"
            wav = wavs / f"{index:03d}.wav"
            await _save_upload(upload, raw, max_bytes)
            added.append(raw)
            try:
                await asyncio.to_thread(transcode, raw, wav, sample_rate=44100, channels=1)
                info = await asyncio.to_thread(probe, wav)
            except AudioError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            added.append(wav)
            total_duration += info["duration"]
            saved.append(
                {
                    "name": upload.filename,
                    "file": str(wav.relative_to(root)),
                    "duration": round(info["duration"], 2),
                }
            )
    except Exception:
        for path in added:
            path.unlink(missing_ok=True)
        raise
    return saved, total_duration


def _invalidate_dataset(meta: dict, root: Path) -> None:
    """素材变化后，旧的切片和训练包作废。"""
    meta["dataset_report"] = None
    meta["training_pack"] = None
    (root / "training_pack.zip").unlink(missing_ok=True)
    slices = root / "dataset" / "slices"
    if slices.exists():
        for path in slices.glob("*.wav"):
            path.unlink()


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
    root.mkdir(parents=True, exist_ok=True)
    try:
        saved, total_duration = await _store_files(root, files, 1)
    except Exception:
        remove_dir(root)
        raise

    warnings = _warnings(total_duration)

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
        "dataset_report": None,
        "training_pack": None,
    }
    write_json(root / "meta.json", meta)
    return {**meta, "warnings": warnings}


@router.post("/{voice_id}/files")
async def add_voice_files(voice_id: str, files: list[UploadFile] = File(...)) -> dict:
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json")
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个音频文件")

    wavs = root / "dataset" / "wav"
    start = _next_index(wavs)
    saved, duration = await _store_files(root, files, start)
    meta["files"] = list(meta.get("files", [])) + saved
    meta["total_duration"] = round(meta.get("total_duration", 0.0) + duration, 2)
    _invalidate_dataset(meta, root)
    write_json(root / "meta.json", meta)
    return {**meta, "warnings": _warnings(meta["total_duration"])}


@router.post("/{voice_id}/prepare")
async def prepare_voice(
    voice_id: str,
    min_len: float = 3.0,
    max_len: float = 10.0,
) -> dict:
    if not (1.0 <= min_len < max_len <= 30.0):
        raise HTTPException(status_code=400, detail="切片长度参数不合法")
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json")
    try:
        report = await asyncio.to_thread(
            prepare_training_pack, root, min_len=min_len, max_len=max_len
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    meta["dataset_report"] = report
    meta["training_pack"] = report["pack_path"]
    write_json(root / "meta.json", meta)
    return {**report, "voice_id": voice_id}


@router.get("/{voice_id}/training-pack")
def download_training_pack(voice_id: str) -> FileResponse:
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json")
    pack = root / "training_pack.zip"
    if not pack.exists():
        raise HTTPException(status_code=404, detail="训练包还没生成，请先准备训练")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", meta.get("name", "voice"))
    return FileResponse(
        pack,
        media_type="application/zip",
        filename=f"{safe_name}_rvc_dataset.zip",
    )


@router.post("/{voice_id}/model")
async def import_model(
    voice_id: str,
    pth: UploadFile = File(...),
    index: UploadFile | None = File(None),
) -> dict:
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json")

    if Path(pth.filename or "").suffix.lower() != ".pth":
        raise HTTPException(status_code=400, detail="模型文件必须是 .pth")
    if index is not None and Path(index.filename or "").suffix.lower() != ".index":
        raise HTTPException(status_code=400, detail="索引文件必须是 .index")

    model_dir = root / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    pth_path = model_dir / "model.pth"
    await _save_upload(pth, pth_path, max_bytes)
    with pth_path.open("rb") as fh:
        magic = fh.read(4)
    if magic[:2] not in (b"PK", b"\x80\x02"):
        pth_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="这个 .pth 不是有效的 RVC 模型文件")

    index_info = None
    if index is not None:
        index_path = model_dir / "model.index"
        await _save_upload(index, index_path, max_bytes)
        index_info = {"file": "model/model.index", "bytes": index_path.stat().st_size}

    meta["has_model"] = True
    meta["model"] = {
        "pth": "model/model.pth",
        "pth_bytes": pth_path.stat().st_size,
        "index": index_info,
        "imported_at": now_iso(),
    }
    write_json(root / "meta.json", meta)
    return meta


@router.delete("/{voice_id}/model")
def delete_model(voice_id: str) -> dict:
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json")
    for name in ("model.pth", "model.index"):
        (root / "model" / name).unlink(missing_ok=True)
    meta["has_model"] = False
    meta["model"] = None
    write_json(root / "meta.json", meta)
    return meta


@router.get("/{voice_id}")
def get_voice(voice_id: str) -> dict:
    return read_json(_root_for(voice_id) / "meta.json")


@router.delete("/{voice_id}")
def delete_voice(voice_id: str) -> dict:
    remove_dir(_root_for(voice_id))
    return {"ok": True}
