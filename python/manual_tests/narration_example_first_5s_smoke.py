#!/usr/bin/env python3
"""
本地冒烟：使用仓库根目录的 ``example.mp4``，只处理前 **5 秒** 区间（0s–5s）。

- 默认：校验片段时长、用 ffmpeg 抽若干帧（不落盘，仅统计），**不调用**大模型。
- 加 ``--narrate``：再调用旁白生成（需配置所选 ``narration_provider`` 对应密钥与 Base URL，见 movieteller_config）。

在仓库根目录执行（与 movieteller_config 加载方式一致，cwd 建议为根目录）::

    pip install -e python/movieteller_config
    # 若尚未安装 narration 包，用 PYTHONPATH 即可
    PYTHONPATH=python/movieteller_config/src:python/narration/src \\
        python3 python/manual_tests/narration_example_first_5s_smoke.py

    PYTHONPATH=python/movieteller_config/src:python/narration/src \\
        python3 python/manual_tests/narration_example_first_5s_smoke.py --narrate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_paths() -> None:
    root = _repo_root()
    for sub in (
        root / "python" / "movieteller_config" / "src",
        root / "python" / "narration" / "src",
    ):
        if sub.is_dir():
            sys.path.insert(0, str(sub))


def main() -> int:
    _ensure_paths()

    from movieteller_config import load_settings
    from narration.frames import (
        extract_frames_base64,
        ffprobe_path_for,
        segment_duration_sec,
    )

    ap = argparse.ArgumentParser(description="example.mp4 前 5s 抽帧 / 可选旁白")
    ap.add_argument(
        "--narrate",
        action="store_true",
        help="调用多模态旁白（需 API 配置）",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON（仅非 --narrate 时含 duration、frame_count、base64 总长度等）",
    )
    args = ap.parse_args()

    root = _repo_root()
    video = root / "example.mp4"
    if not video.is_file():
        print(f"未找到 {video}，请将测试用 MP4 放在仓库根目录。", file=sys.stderr)
        return 1

    settings = load_settings(require_narration=args.narrate)
    start, end = 0.0, 5.0
    ffprobe = ffprobe_path_for(settings.ffmpeg_path)
    duration = segment_duration_sec(
        str(video), start, end, ffprobe_bin=ffprobe
    )

    frames = extract_frames_base64(
        str(video),
        start_sec=start,
        end_sec=end,
        duration_sec=duration,
        max_frames=settings.max_frames_per_segment,
        ffmpeg_bin=settings.ffmpeg_path,
        max_edge_pixels=settings.narration_frame_max_edge,
    )

    if args.narrate:
        from narration import narrate_segment

        text = narrate_segment(
            str(video),
            start,
            end,
            settings=settings,
        )
        if args.json:
            print(
                json.dumps(
                    {"text": text, "duration_sec": duration, "frame_count": len(frames)},
                    ensure_ascii=False,
                )
            )
        else:
            print(text)
        return 0

    out = {
        "video": str(video),
        "start_sec": start,
        "end_sec": end,
        "duration_sec": duration,
        "frame_count": len(frames),
        "base64_total_chars": sum(len(x) for x in frames),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: {video.name} 0s–5s, duration={duration:.3f}s, "
            f"frames={len(frames)}, max_edge={settings.narration_frame_max_edge}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
