"""混音与导出：人声 + 伴奏，响度归一化，输出 WAV / MP3。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from ..config import settings


def _read(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True, dtype="float32")
    if data.size == 0:
        raise ValueError(f"空音频: {path}")
    return data, sr


def _to_stereo(data: np.ndarray) -> np.ndarray:
    if data.shape[1] == 1:
        return np.repeat(data, 2, axis=1)
    return data[:, :2]


def mix_audio(
    vocals_path: Path,
    instrumental_path: Path,
    out_wav: Path,
    *,
    vocal_gain_db: float = 0.0,
    instrumental_gain_db: float = 0.0,
    target_lufs: float = -14.0,
    peak_db: float = -1.0,
) -> dict:
    """按增益混合两轨，做 LUFS 归一化与峰值保护，写 16bit WAV。"""
    vocals, sr = _read(vocals_path)
    instrumental, sr2 = _read(instrumental_path)
    if sr != sr2:
        raise ValueError(f"采样率不一致: {sr} vs {sr2}")

    vocals = _to_stereo(vocals) * (10 ** (vocal_gain_db / 20))
    instrumental = _to_stereo(instrumental) * (10 ** (instrumental_gain_db / 20))

    length = max(len(vocals), len(instrumental))
    mix = np.zeros((length, 2), dtype=np.float32)
    mix[: len(vocals)] += vocals
    mix[: len(instrumental)] += instrumental

    # 响度归一化；太短的音频跳过，避免 pyloudnorm 报错。
    if length / sr >= 0.5:
        meter = pyln.Meter(sr)
        loudness = meter.integrated_loudness(mix)
        if np.isfinite(loudness) and loudness > -70:
            mix *= 10 ** ((target_lufs - loudness) / 20)

    peak_limit = 10 ** (peak_db / 20)
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > peak_limit:
        mix *= peak_limit / peak

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), mix, sr, subtype="PCM_16")

    return {
        "output": str(out_wav),
        "sample_rate": sr,
        "duration": round(length / sr, 2),
        "peak": round(float(np.max(np.abs(mix))), 4),
    }


def export_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "320k") -> Path:
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(mp3_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        raise RuntimeError(f"MP3 导出失败: {' | '.join(detail[-2:])}")
    return mp3_path
