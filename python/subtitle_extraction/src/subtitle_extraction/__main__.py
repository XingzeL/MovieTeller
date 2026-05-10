from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cue_to_json(c) -> dict:
    return {"startSec": c.start_sec, "endSec": c.end_sec, "text": c.text}


def main() -> int:
    ap = argparse.ArgumentParser(description="MovieTeller subtitle extraction via videocaptioner transcribe")
    ap.add_argument("--video", required=True, help="Local video or audio file path")
    ap.add_argument("--output-srt", default=None, help="Write SRT to this path (default: same stem as video)")
    ap.add_argument("--asr", default=None, help="Override ASR (bijian|jianying|whisper-api|whisper-cpp)")
    ap.add_argument("--language", default=None, help="Source language or auto")
    ap.add_argument("--json", action="store_true", help="Print JSON (subtitlePath + cues) to stdout")
    args = ap.parse_args()

    try:
        from movieteller_config import load_settings
    except ImportError:
        print("movieteller_config required (pip install -e python/movieteller_config)", file=sys.stderr)
        return 1

    from subtitle_extraction.transcribe import TranscriptionError, extract_subtitles

    settings = load_settings()
    out_srt = args.output_srt
    if out_srt is None:
        out_srt = str(Path(args.video).with_suffix(".srt"))

    timeout_ms = getattr(settings, "videocaptioner_transcribe_timeout_ms", None)
    timeout_sec = None if timeout_ms is None else max(1.0, float(timeout_ms) / 1000.0)

    try:
        result = extract_subtitles(
            args.video,
            videocaptioner_bin=getattr(settings, "videocaptioner_bin", None),
            output_srt_path=out_srt,
            asr=(args.asr or getattr(settings, "videocaptioner_asr", None) or "bijian"),
            language=(args.language or getattr(settings, "videocaptioner_language", None) or "auto"),
            timeout_sec=timeout_sec,
        )
    except TranscriptionError as e:
        print(str(e), file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return 2

    payload = {
        "subtitlePath": result.subtitle_path,
        "cues": [_cue_to_json(c) for c in result.cues],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(result.subtitle_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
