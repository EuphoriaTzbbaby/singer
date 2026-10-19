"""远程录音：带令牌的录音页 + 上传接口，文件只保存在本机。

上传只负责保存和转码；切片较慢，放到后台任务，页面轮询状态。
"""

from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..pipeline.dataset import prepare_training_pack
from ..storage import new_id, now_iso, read_json, remove_dir, voice_dir, write_json
from .voices import _root_for, _store_files, _warnings

router = APIRouter(tags=["recordings"])


def _check_token(token: str) -> None:
    expected = settings.ensure_record_token()
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="录音链接无效或已过期")


async def _prepare_voice(root: Path) -> None:
    meta = read_json(root / "meta.json") or {}
    try:
        report = await asyncio.to_thread(prepare_training_pack, root)
        meta["dataset_report"] = report
        meta["training_pack"] = report.get("pack_path")
        meta["prepare_status"] = "ready"
        meta["prepare_error"] = None
    except Exception as exc:  # noqa: BLE001
        meta["prepare_status"] = "failed"
        meta["prepare_error"] = str(exc)
    write_json(root / "meta.json", meta)


@router.get("/record")
def record_page(token: str = "") -> FileResponse:
    _check_token(token)
    return FileResponse(settings.static_dir / "record.html")


@router.get("/api/record-link")
def record_link(request: Request) -> dict:
    token = settings.ensure_record_token()
    base = str(request.base_url).rstrip("/")
    host = request.url.hostname or ""
    return {
        "url": f"{base}/record?token={token}",
        "host": host,
        "localhost": host in {"127.0.0.1", "localhost", "::1"},
    }


@router.post("/api/recordings")
async def upload_recording(
    background_tasks: BackgroundTasks,
    token: str = Form(...),
    name: str = Form(..., min_length=1, max_length=60),
    consent: bool = Form(False),
    mode: str = Form("standard"),
    file: UploadFile = File(...),
) -> dict:
    _check_token(token)
    if not consent:
        raise HTTPException(status_code=400, detail="必须确认声音为本人所有或已获授权")
    if mode not in {"standard", "easy"}:
        mode = "standard"

    voice_id = new_id("voice")
    root = voice_dir(voice_id)
    root.mkdir(parents=True, exist_ok=True)

    try:
        saved, duration = await _store_files(root, [file], 1)
    except HTTPException:
        remove_dir(root)
        raise
    except Exception as exc:  # noqa: BLE001
        remove_dir(root)
        raise HTTPException(status_code=500, detail=f"保存录音失败: {exc}") from exc

    meta = {
        "id": voice_id,
        "name": name.strip(),
        "created_at": now_iso(),
        "consent_at": now_iso(),
        "kind": "rvc_dataset",
        "source": "web_recording",
        "recording_mode": mode,
        "files": saved,
        "total_duration": round(duration, 2),
        "has_model": False,
        "model": None,
        "dataset_report": None,
        "training_pack": None,
        "prepare_status": "processing",
        "prepare_error": None,
    }
    write_json(root / "meta.json", meta)
    background_tasks.add_task(_prepare_voice, root)

    return {
        "voice_id": voice_id,
        "name": meta["name"],
        "duration": meta["total_duration"],
        "status": "processing",
        "mode": mode,
    }


@router.get("/api/recordings/{voice_id}/status")
def recording_status(voice_id: str, token: str = "") -> dict:
    _check_token(token)
    root = _root_for(voice_id)
    meta = read_json(root / "meta.json") or {}
    report = meta.get("dataset_report") or {}
    status = meta.get("prepare_status") or ("ready" if report else "unknown")
    warnings = report.get("warnings") if report else _warnings(meta.get("total_duration", 0))
    return {
        "voice_id": voice_id,
        "name": meta.get("name"),
        "status": status,
        "duration": meta.get("total_duration"),
        "clip_count": report.get("clip_count"),
        "total_seconds": report.get("total_seconds"),
        "warnings": warnings or [],
        "error": meta.get("prepare_error"),
    }
