from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline_transcript.speech_video_script import (
    PipelineSpeechVideoScriptOptions,
    build_readable_script,
    load_pipeline_speech_video_json,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convert *.pipeline.speech_video.json to a human-readable script (stdout or file)."
    )
    ap.add_argument(
        "input_json",
        type=Path,
        help="Path to pipeline speech_video JSON",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write script to this path (UTF-8). Default: print to stdout",
    )
    ap.add_argument("--title", default=None, help="Override document title line")
    ap.add_argument(
        "--no-raw-narration",
        action="store_true",
        help="Do not emit vision 'text' when it differs from speechText",
    )
    ap.add_argument(
        "--speech-meta",
        action="store_true",
        help="Append one-line TTS metadata (voice, fitApplied) per segment",
    )
    args = ap.parse_args(argv)

    payload = load_pipeline_speech_video_json(args.input_json)
    text = build_readable_script(
        payload,
        source_path=args.input_json,
        options=PipelineSpeechVideoScriptOptions(
            title=args.title,
            include_raw_narration_if_different=not args.no_raw_narration,
            include_speech_meta_one_liner=args.speech_meta,
        ),
    )
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
