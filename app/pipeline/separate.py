"""Demucs 人声分离。

调用 demucs 官方 CLI，输出 vocals / no_vocals 两轨。
Apple Silicon 默认用 MPS，失败时自动回退 CPU。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..config import settings


class SeparationError(RuntimeError):
    pass


def subprocess_env() -> dict[str, str]:
    """把模型缓存固定到项目内，避免写入 ~/.cache 失败。"""
    env = os.environ.copy()
    env.setdefault("TORCH_HOME", str(settings.torch_home))
    env.setdefault("XDG_CACHE_HOME", str(settings.cache_dir / "xdg"))
    env.setdefault("HF_HOME", str(settings.cache_dir / "huggingface"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _default_device() -> str:
    if settings.demucs_device != "auto":
        return settings.demucs_device
    try:
        import torch

        return "mps" if torch.backends.mps.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def _run_demucs(
    song_wav: Path,
    out_root: Path,
    model: str,
    device: str,
    timeout: int,
) -> None:
    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "-n",
        model,
        "--two-stems=vocals",
        "-d",
        device,
        "-o",
        str(out_root),
        str(song_wav),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=subprocess_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SeparationError(f"人声分离超时（{timeout}s）") from exc

    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " | ".join(line.strip() for line in lines[-4:] if line.strip())
        raise SeparationError(f"Demucs 失败（{device}）: {tail or '未知错误'}")


def separate_song(
    song_wav: Path,
    out_root: Path | None = None,
    *,
    model: str | None = None,
    device: str | None = None,
    timeout: int = 3600,
) -> dict[str, str]:
    """分离歌曲，返回 {"vocals": path, "instrumental": path, "device": ...}。"""
    song_wav = song_wav.resolve()
    if not song_wav.exists():
        raise SeparationError(f"找不到歌曲文件: {song_wav}")

    out_root = (out_root or song_wav.parent / "stems").resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    model = model or settings.demucs_model
    device = device or _default_device()

    attempts = [device]
    if device != "cpu":
        attempts.append("cpu")

    last_error: Exception | None = None
    used_device = device
    for attempt in attempts:
        try:
            _run_demucs(song_wav, out_root, model, attempt, timeout)
            used_device = attempt
            last_error = None
            break
        except SeparationError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    track_dir = out_root / model / song_wav.stem
    vocals = track_dir / "vocals.wav"
    instrumental = track_dir / "no_vocals.wav"
    if not vocals.exists() or not instrumental.exists():
        raise SeparationError(f"分离完成但找不到输出文件: {track_dir}")

    return {
        "vocals": str(vocals),
        "instrumental": str(instrumental),
        "device": used_device,
        "model": model,
    }
