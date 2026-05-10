from __future__ import annotations

import argparse
import json

from narration_video.render import render_narrated_video
from narration_video.types import NarrationAudioSegment


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Embed narration audio segments into a source video."
    )
    ap.add_argument("--video", required=True, help="Source video path")
    ap.add_argument("--output", required=True, help="Rendered output video path")
    ap.add_argument(
        "--segment",
        action="append",
        nargs=3,
        metavar=("START_SEC", "END_SEC", "AUDIO_PATH"),
        help="Narration audio segment triplet; may be repeated",
    )
    ap.add_argument(
        "--background-audio-volume",
        type=float,
        default=None,
        help="Volume multiplier for original video audio",
    )
    ap.add_argument(
        "--speech-audio-volume",
        type=float,
        default=None,
        help="Volume multiplier for narration audio tracks",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON payload")
    args = ap.parse_args()

    if not args.segment:
        ap.error("at least one --segment START_SEC END_SEC AUDIO_PATH is required")
    segments = [
        NarrationAudioSegment(
            start_sec=float(item[0]),
            end_sec=float(item[1]),
            audio_path=item[2],
        )
        for item in args.segment
    ]
    result = render_narrated_video(
        args.video,
        segments,
        output_path=args.output,
        background_audio_volume=args.background_audio_volume,
        speech_audio_volume=args.speech_audio_volume,
    )
    payload = {
        "videoPath": result.video_path,
        "outputPath": result.output_path,
        "segmentCount": result.segment_count,
        "videoDurationSec": result.video_duration_sec,
        "backgroundAudioVolume": result.background_audio_volume,
        "speechAudioVolume": result.speech_audio_volume,
        "timingRenderSec": result.timing_render_sec,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            f"{payload['outputPath']} segments={payload['segmentCount']} "
            f"render={payload['timingRenderSec']:.3f}s"
        )
    return 0
