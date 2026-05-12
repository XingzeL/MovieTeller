from __future__ import annotations

import argparse
import json

from subtitle_analysis.analyze import analyze_subtitle_file, result_to_dict


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Analyze SRT subtitle coverage and derive no-subtitle narration candidates."
    )
    ap.add_argument("--srt", required=True, help="Path to extracted .srt file")
    ap.add_argument("--video", default=None, help="Optional media path for probing full duration")
    ap.add_argument(
        "--duration-sec",
        type=float,
        default=None,
        help="Optional explicit full video duration in seconds",
    )
    ap.add_argument(
        "--min-gap-sec",
        type=float,
        default=1.0,
        help="Minimum gap duration after trimming to keep as narration candidate",
    )
    ap.add_argument(
        "--subtitle-guard-sec",
        type=float,
        default=0.25,
        help="Trim this many seconds away from subtitle boundaries",
    )
    ap.add_argument("--ffprobe-bin", default="ffprobe", help="ffprobe executable path")
    ap.add_argument("--json", action="store_true", help="Print JSON payload")
    args = ap.parse_args()

    result = analyze_subtitle_file(
        args.srt,
        video_path=args.video,
        video_duration_sec=args.duration_sec,
        min_gap_sec=args.min_gap_sec,
        subtitle_guard_sec=args.subtitle_guard_sec,
        ffprobe_bin=args.ffprobe_bin,
    )
    payload = result_to_dict(result)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            f"subtitle_spans={len(payload['subtitleSpans'])} "
            f"raw_gaps={len(payload['rawGaps'])} "
            f"narration_candidates={len(payload['narrationCandidates'])}"
        )
        for seg in payload["narrationCandidates"]:
            print(
                f"{seg['startSec']:.3f}-{seg['endSec']:.3f}s "
                f"({seg['durationSec']:.3f}s)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
