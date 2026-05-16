#!/usr/bin/env python3
"""
本地冒烟：使用仓库根目录的 ``example.mp4``，只处理前 **5 秒** 区间（0s–5s）。

- 默认：校验片段时长、用 ffmpeg 抽若干帧（不落盘，仅统计），**不调用**大模型。
- 加 ``--narrate``：再调用旁白生成（需配置 gateway 默认 provider、对应 key/base URL 和 narration 默认模型，见 movieteller_config）。

在仓库根目录执行（与 movieteller_config 加载方式一致，cwd 建议为根目录）::

    source .venv/bin/activate
    python -m pip install -e python/movieteller_config -e python/narration
    # 若尚未安装 narration 包，用 PYTHONPATH 即可
    PYTHONPATH=python/movieteller_config/src:python/narration/src \\
        python python/manual_tests/narration_example_first_5s_smoke.py

    PYTHONPATH=python/movieteller_config/src:python/narration/src \\
        python python/manual_tests/narration_example_first_5s_smoke.py --narrate
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _log_timing(message: str) -> None:
    """Timing lines go to stderr so ``--json`` stdout stays parseable."""
    print(message, file=sys.stderr)


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
    from frame_source import FrameSourceOptions
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
    ap.add_argument(
        "--model",
        default=None,
        metavar="MODEL_ID",
        help="覆盖本次请求的模型 id（等价 narrate_segment 的 image_model；可选）",
    )
    args = ap.parse_args()

    root = _repo_root()
    video = root / "example.mp4"
    if not video.is_file():
        print(f"未找到 {video}，请将测试用 MP4 放在仓库根目录。", file=sys.stderr)
        return 1

    settings = load_settings(require_narration=args.narrate)
    start, end = 1.0, 10.0
    ffprobe = ffprobe_path_for(settings.ffmpeg_path)
    duration = segment_duration_sec(
        str(video), start, end, ffprobe_bin=ffprobe
    )

    if args.narrate:
        from narration import narrate_segment_with_duration

        timings: dict[str, Any] = {}
        t0 = time.perf_counter()
        narration_options = settings.narration_options(model=args.model)
        frame_source_options = FrameSourceOptions(
            ffmpeg_bin=settings.ffmpeg_path,
            max_frames_per_segment=settings.max_frames_per_segment,
            max_edge_pixels=settings.narration_frame_max_edge,
            pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
            allow_uniform_fallback=True,
        )
        text, duration = narrate_segment_with_duration(
            str(video),
            start,
            end,
            options=narration_options,
            frame_source_options=frame_source_options,
            settings=settings,
            timings_out=timings,
        )
        wall_total = time.perf_counter() - t0
        extract_sec = timings.get("extract_sec", 0.0)
        api_sec = timings.get("api_sec", 0.0)
        frame_count = int(timings.get("frame_count", 0))
        _log_timing(
            f"[timing] extract_frames_base64: {extract_sec:.3f}s | "
            f"generate_narration (API): {api_sec:.3f}s | "
            f"narrate_segment_with_duration (reported total): {timings.get('total_sec', 0.0):.3f}s | "
            f"wall inclusive: {wall_total:.3f}s | frames={frame_count}"
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "text": text,
                        "duration_sec": duration,
                        "frame_count": frame_count,
                        "timing_extract_sec": extract_sec,
                        "timing_api_sec": api_sec,
                        "timing_total_sec": timings.get("total_sec", 0.0),
                        "timing_wall_sec": wall_total,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(text)
        return 0

    # 抽帧，得到 base64 编码的 PNG，一共 max_frames_per_segment 帧
    t_extract0 = time.perf_counter()
    frames = extract_frames_base64(
        str(video),
        start_sec=start,
        end_sec=end,
        duration_sec=duration,
        max_frames=settings.max_frames_per_segment,
        ffmpeg_bin=settings.ffmpeg_path,
        max_edge_pixels=settings.narration_frame_max_edge,
    )
    extract_sec = time.perf_counter() - t_extract0
    _log_timing(f"[timing] extract_frames_base64: {extract_sec:.3f}s (frames={len(frames)})")

    out = {
        "video": str(video),
        "start_sec": start,
        "end_sec": end,
        "duration_sec": duration,
        "frame_count": len(frames),
        "base64_total_chars": sum(len(x) for x in frames),
        "timing_extract_sec": extract_sec,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: {video.name} 5s–10s, duration={duration:.3f}s, "
            f"frames={len(frames)}, max_edge={settings.narration_frame_max_edge}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
