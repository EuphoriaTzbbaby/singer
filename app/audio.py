"""音频基础操作：探测、转码、时长。

全部通过 ffmpeg / ffprobe 完成，避免为了转码再引入额外依赖。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import settings

AUDIO_EXTS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".webm",
    ".mp4",
}


class AudioError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AudioError(f"找不到命令: {cmd[0]}，请先安装 ffmpeg") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f"音频处理超时（{timeout}s）") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " | ".join(detail[-3:]) if detail else "未知错误"
        raise AudioError(f"ffmpeg 失败: {tail}")
    return proc


def probe(path: Path) -> dict:
    """返回时长、采样率、声道数。"""
    proc = _run(
        [
            settings.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=sample_rate,channels,codec_type",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
    )
    info = json.loads(proc.stdout or "{}")
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise AudioError("文件里没有音频流")
    stream = streams[0]
    try:
        duration = float(info.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "duration": duration,
        "sample_rate": int(stream.get("sample_rate", 0)),
        "channels": int(stream.get("channels", 0)),
    }


def transcode(
    src: Path,
    dst: Path,
    *,
    sample_rate: int = 44100,
    channels: int = 2,
    loudnorm: bool = False,
) -> Path:
    """转成 PCM WAV；loudnorm 使用 EBU R128 单遍归一化。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    filters = ["loudnorm=I=-16:TP=-1.5:LRA=11"] if loudnorm else []
    cmd = [
        settings.ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vn",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        "-c:a",
        "pcm_s16le",
    ]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd.append(str(dst))
    _run(cmd)
    if not dst.exists() or dst.stat().st_size == 0:
        raise AudioError("转码后文件为空")
    return dst
