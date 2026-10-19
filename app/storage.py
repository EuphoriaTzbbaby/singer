"""极简文件存储：每个音色 / 歌曲 / 任务一个目录，元数据存 meta.json。

不引入数据库，方便本地运行、备份和直接查看。
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{secrets.token_hex(3)}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def voice_dir(voice_id: str) -> Path:
    return settings.voices_dir / voice_id


def song_dir(song_id: str) -> Path:
    return settings.songs_dir / song_id


def job_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def list_items(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    items = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        meta = read_json(child / "meta.json")
        if meta:
            items.append(meta)
    return sorted(items, key=lambda m: m.get("created_at", ""), reverse=True)


def remove_dir(path: Path) -> None:
    resolved = path.resolve()
    base = settings.data_dir.resolve()
    if base not in resolved.parents:
        raise ValueError(f"拒绝删除数据目录之外的路径: {resolved}")
    shutil.rmtree(resolved, ignore_errors=True)
