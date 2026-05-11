from __future__ import annotations

import argparse
import json
import sys

from video_frame_pool.build import build_frame_pool


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m video_frame_pool",
        description="Build a stage-1 frame pool for MovieTeller narration.",
    )
    ap.add_argument("--video", required=True, help="Local video path")
    ap.add_argument("--srt", required=True, help="Extracted subtitle .srt path")
    ap.add_argument(
        "--output-dir",
        default=None,
        help="Output frame-pool directory (default: <video-stem>.frame_pool)",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON payload")
    args = ap.parse_args(argv)

    try:
        result = build_frame_pool(
            video_path=args.video,
            srt_path=args.srt,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        msg = str(exc) or exc.__class__.__name__
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stdout)
        else:
            print(msg, file=sys.stderr)
        return 1

    payload = {
        "outputDir": result.output_dir,
        "manifestPath": result.manifest_path,
        "shotsPath": result.shots_path,
        "shotCount": result.shot_count,
        "nonDialogueShotCount": result.non_dialogue_shot_count,
        "frameCount": result.frame_count,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(result.manifest_path)
    return 0
