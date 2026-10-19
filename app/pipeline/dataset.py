"""训练素材处理：切片、质检、导出训练包。

做三件事：
1. 按静音切分长录音，合并/拆分到 3–10 秒；
2. 统一响度、去爆音、统计质量指标；
3. 打包成可直接上传 Colab 的 zip。
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from ..storage import now_iso

SAMPLE_RATE = 44100


def _load_mono(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        mono = librosa.resample(mono, orig_sr=sr, target_sr=SAMPLE_RATE)
    return mono


def _min_energy_cut(y: np.ndarray, lo: int, hi: int) -> int:
    """在 [lo, hi) 内找能量最低的位置作为切点。"""
    if hi - lo < 2048:
        return (lo + hi) // 2
    rms = librosa.feature.rms(y=y[lo:hi], frame_length=2048, hop_length=441)[0]
    idx = int(np.argmin(rms))
    return lo + idx * 441 + 1024


def _split_intervals(y: np.ndarray, sr: int, top_db: float) -> list[tuple[int, int]]:
    intervals = librosa.effects.split(y, top_db=top_db, frame_length=2048, hop_length=512)
    return [(int(s), int(e)) for s, e in intervals if e > s]


def _merge_gaps(
    intervals: list[tuple[int, int]], sr: int, max_len: float, gap: float = 0.25
) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= gap * sr and end - prev_start <= max_len * sr:
                merged[-1] = (prev_start, end)
                continue
        merged.append((start, end))
    return merged


def _split_long(
    intervals: list[tuple[int, int]], y: np.ndarray, sr: int, min_len: float, max_len: float
) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for start, end in intervals:
        while end - start > max_len * sr:
            target = start + int(max_len * sr)
            lo = max(start + int(min_len * sr), target - int(0.75 * sr))
            hi = min(end, target + int(0.75 * sr))
            cut = _min_energy_cut(y, lo, hi)
            if cut <= start + int(0.5 * sr):
                cut = target
            out.append((start, cut))
            start = cut
        if end - start > 0:
            out.append((start, end))
    return out


def _merge_short(
    intervals: list[tuple[int, int]], sr: int, min_len: float, max_len: float, gap: float = 0.5
) -> list[tuple[int, int]]:
    changed = True
    while changed:
        changed = False
        merged: list[tuple[int, int]] = []
        index = 0
        while index < len(intervals):
            start, end = intervals[index]
            if index + 1 < len(intervals):
                next_start, next_end = intervals[index + 1]
                too_short = (end - start < min_len * sr) or (next_end - next_start < min_len * sr)
                if too_short and next_end - start <= max_len * sr and next_start - end <= gap * sr:
                    merged.append((start, next_end))
                    index += 2
                    changed = True
                    continue
            merged.append((start, end))
            index += 1
        intervals = merged
    return intervals


def _normalize_clip(clip: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    if len(clip) / sr >= 0.4:
        meter = pyln.Meter(sr)
        loudness = meter.integrated_loudness(clip)
        if np.isfinite(loudness) and loudness > -70:
            clip = clip * (10 ** ((target_lufs - loudness) / 20))
    peak_limit = 10 ** (-1 / 20)
    peak = float(np.max(np.abs(clip))) if clip.size else 0.0
    if peak > peak_limit:
        clip = clip * (peak_limit / peak)
    return clip.astype(np.float32)


def _fade(clip: np.ndarray, sr: int) -> np.ndarray:
    length = min(int(0.01 * sr), len(clip) // 2)
    if length < 8:
        return clip
    ramp = np.linspace(0.0, 1.0, length, dtype=np.float32)
    clip[:length] *= ramp
    clip[-length:] *= ramp[::-1]
    return clip


def _warn(report: dict) -> list[str]:
    warnings: list[str] = []
    if report["source_seconds"] < 300:
        warnings.append("素材总时长不足 5 分钟，训练效果会很有限。")
    elif report["source_seconds"] < 600:
        warnings.append("素材少于 10 分钟，可以训练；10–15 分钟效果更稳。")
    if report["clip_count"] < 50:
        warnings.append("切片少于 50 段，建议补充更多素材。")
    if report["clipped_ratio"] > 0.001:
        warnings.append("检测到削波，录音音量偏大，建议降低输入增益重录。")
    if report["clip_count"] and report["avg_seconds"] < 2.5:
        warnings.append("平均片段偏短，可能影响训练稳定性。")
    if report["silence_ratio"] > 0.6:
        warnings.append("静音占比过高，请检查录音是否有长时间空白。")
    return warnings


def prepare_training_pack(
    voice_root: Path,
    *,
    min_len: float = 3.0,
    max_len: float = 10.0,
    top_db: float = 35.0,
    target_lufs: float = -18.0,
) -> dict:
    """切片并生成 training_pack.zip，返回质检报告。"""
    source_dir = voice_root / "dataset" / "wav"
    sources = sorted(source_dir.glob("*.wav"))
    if not sources:
        raise ValueError("没有可用的素材，请先上传录音")

    slices_dir = voice_root / "dataset" / "slices"
    if slices_dir.exists():
        for old in slices_dir.glob("*.wav"):
            old.unlink()
    slices_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[Path] = []
    source_seconds = 0.0
    clipped_samples = 0
    total_samples = 0
    speech_samples = 0

    for source in sources:
        y = _load_mono(source)
        source_seconds += len(y) / SAMPLE_RATE
        total_samples += len(y)
        clipped_samples += int(np.sum(np.abs(y) >= 0.999))

        intervals = _split_intervals(y, SAMPLE_RATE, top_db)
        speech_samples += sum(end - start for start, end in intervals)
        intervals = _merge_gaps(intervals, SAMPLE_RATE, max_len)
        intervals = _split_long(intervals, y, SAMPLE_RATE, min_len, max_len)
        intervals = _merge_short(intervals, SAMPLE_RATE, min_len, max_len)
        intervals = [
            (start, end) for start, end in intervals if (end - start) / SAMPLE_RATE >= min_len * 0.6
        ]

        pad = int(0.05 * SAMPLE_RATE)
        for start, end in intervals:
            start = max(0, start - pad)
            end = min(len(y), end + pad)
            clip = _normalize_clip(y[start:end].copy(), SAMPLE_RATE, target_lufs)
            clip = _fade(clip, SAMPLE_RATE)
            index = len(clip_paths) + 1
            path = slices_dir / f"slice_{index:04d}.wav"
            sf.write(str(path), clip, SAMPLE_RATE, subtype="PCM_16")
            clip_paths.append(path)

    lengths = [sf.info(str(path)).duration for path in clip_paths]
    report = {
        "created_at": now_iso(),
        "source_files": len(sources),
        "source_seconds": round(source_seconds, 1),
        "clip_count": len(clip_paths),
        "total_seconds": round(sum(lengths), 1),
        "min_seconds": round(min(lengths), 2) if lengths else 0.0,
        "max_seconds": round(max(lengths), 2) if lengths else 0.0,
        "avg_seconds": round(sum(lengths) / len(lengths), 2) if lengths else 0.0,
        "clipped_ratio": round(clipped_samples / max(total_samples, 1), 6),
        "silence_ratio": round(1 - speech_samples / max(total_samples, 1), 3),
        "sample_rate": SAMPLE_RATE,
        "params": {"min_len": min_len, "max_len": max_len, "top_db": top_db, "target_lufs": target_lufs},
    }
    report["warnings"] = _warn(report)

    if not clip_paths:
        raise ValueError("没有切出有效片段，请检查录音是否过短或音量过低")

    pack_path = voice_root / "training_pack.zip"
    readme = (
        "Singer RVC 训练素材包\n"
        "====================\n\n"
        f"切片数量：{report['clip_count']}\n"
        f"总时长：{report['total_seconds']} 秒\n"
        f"采样率：{SAMPLE_RATE} Hz，单声道，16bit\n\n"
        "使用方法：把本 zip 上传到 Google Drive，在 Colab 中解压后指向 dataset/ 目录训练。\n"
        "详细步骤见项目 docs/TRAINING.md。\n"
    )
    with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in clip_paths:
            zf.write(path, f"dataset/{path.name}")
        zf.writestr("report.json", json.dumps(report, ensure_ascii=False, indent=2))
        zf.writestr("README.txt", readme)

    report["pack_path"] = str(pack_path.relative_to(voice_root))
    report["pack_bytes"] = pack_path.stat().st_size
    report_path = voice_root / "dataset" / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
