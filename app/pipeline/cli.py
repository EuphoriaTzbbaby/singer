"""音频流水线命令行工具（M1 阶段验证用）。

用法：
    python -m app.pipeline.cli separate path/to/song.wav
    python -m app.pipeline.cli mix vocals.wav instrumental.wav out.wav
    python -m app.pipeline.cli demo path/to/song.wav   # 分离 + 原人声回混
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .mix import export_mp3, mix_audio
from .separate import separate_song


def cmd_separate(args: argparse.Namespace) -> int:
    started = time.time()
    result = separate_song(Path(args.song), Path(args.out) if args.out else None, device=args.device)
    result["elapsed"] = round(time.time() - started, 1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_mix(args: argparse.Namespace) -> int:
    out = Path(args.out)
    result = mix_audio(
        Path(args.vocals),
        Path(args.instrumental),
        out,
        vocal_gain_db=args.vocal_gain,
        instrumental_gain_db=args.instrumental_gain,
    )
    if out.suffix.lower() == ".wav":
        mp3 = out.with_suffix(".mp3")
        export_mp3(out, mp3)
        result["mp3"] = str(mp3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    song = Path(args.song).resolve()
    stems = separate_song(song, song.parent / "stems", device=args.device)
    out_dir = song.parent / "outputs"
    out_wav = out_dir / "demo_mix.wav"
    result = mix_audio(Path(stems["vocals"]), Path(stems["instrumental"]), out_wav)
    result["mp3"] = str(export_mp3(out_wav, out_dir / "demo_mix.mp3"))
    result["stems"] = stems
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="singer-pipeline", description="Singer 音频流水线")
    sub = parser.add_subparsers(dest="command", required=True)

    separate = sub.add_parser("separate", help="用 Demucs 分离人声与伴奏")
    separate.add_argument("song", help="输入歌曲 WAV")
    separate.add_argument("--out", help="输出根目录（默认歌曲目录/stems）")
    separate.add_argument("--device", default=None, help="mps / cpu（默认自动）")
    separate.set_defaults(func=cmd_separate)

    mix = sub.add_parser("mix", help="混合人声与伴奏并导出")
    mix.add_argument("vocals")
    mix.add_argument("instrumental")
    mix.add_argument("out")
    mix.add_argument("--vocal-gain", type=float, default=0.0, help="人声增益 dB")
    mix.add_argument("--instrumental-gain", type=float, default=0.0, help="伴奏增益 dB")
    mix.set_defaults(func=cmd_mix)

    demo = sub.add_parser("demo", help="分离 + 原人声回混，验证整条链路")
    demo.add_argument("song")
    demo.add_argument("--device", default=None)
    demo.set_defaults(func=cmd_demo)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
