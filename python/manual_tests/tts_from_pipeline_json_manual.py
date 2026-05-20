#!/usr/bin/env python3
"""
Generate TTS audio only from an existing MovieTeller pipeline JSON.

Edit ``PIPELINE_JSON_PATH`` below, then run:

    python python/manual_tests/tts_from_pipeline_json_manual.py

This script does not rerun subtitle extraction, frame pooling, subtitle context,
or narration. It only reads ``narratedSegments`` from an existing JSON file and
generates speech audio for each segment using the shared TTS capability config.
Input must be a **text-stage** pipeline JSON; output is a **speech-stage** JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Existing pipeline JSON with narratedSegments.
PIPELINE_JSON_PATH = "test_artifacts/harrypotter_long/harrypotter_long.manual.pipeline.text.json"

# Output directory for generated audio. If None, defaults to:
# <pipeline_json_dir>/<video_stem>.narration_audio
AUDIO_OUTPUT_DIR: str | None = None

# Output JSON path after speech is attached. If None, defaults to:
# <pipeline_json_dir>/<pipeline_json_stem>.speech.json
OUTPUT_JSON_PATH: str | None = None

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_paths() -> None:
    root = _repo_root()
    for sub in (
        root / "python" / "movieteller_config" / "src",
        root / "python" / "media_utils" / "src",
        root / "python" / "model_gateway" / "src",
        root / "python" / "narration_speech" / "src",
    ):
        if sub.is_dir():
            sys.path.insert(0, str(sub))
def _default_audio_dir(pipeline_json_path: Path, payload: dict[str, object]) -> Path:
    artifacts = payload.get("workflowArtifacts")
    video_stem = None
    if isinstance(artifacts, dict):
        video_path = artifacts.get("videoPath")
        if isinstance(video_path, str) and video_path.strip():
            video_stem = Path(video_path).stem
    if not video_stem:
        video_stem = pipeline_json_path.stem.removesuffix(".manual.pipeline")
    return pipeline_json_path.parent / f"{video_stem}.narration_audio"


def main() -> int:
    _ensure_paths()

    from movie_pipeline import (
        parse_pipeline_text_json_path,
        serialize_pipeline_speech_payload,
        synthesize_speech_from_text_payload,
    )
    from movieteller_config import load_settings

    root = _repo_root()
    pipeline_json_path = (root / PIPELINE_JSON_PATH).resolve()
    if not pipeline_json_path.is_file():
        print(f"Pipeline JSON not found: {pipeline_json_path}", file=sys.stderr)
        return 1

    payload = parse_pipeline_text_json_path(pipeline_json_path)

    settings = load_settings()
    speech_options = settings.narration_speech_options()

    audio_output_dir = (
        (root / AUDIO_OUTPUT_DIR).resolve()
        if AUDIO_OUTPUT_DIR is not None
        else _default_audio_dir(pipeline_json_path, payload).resolve()
    )
    audio_output_dir.mkdir(parents=True, exist_ok=True)

    output_json_path = (
        (root / OUTPUT_JSON_PATH).resolve()
        if OUTPUT_JSON_PATH is not None
        else pipeline_json_path.with_name(f"{pipeline_json_path.stem}.speech.json")
    )
    speech_payload = synthesize_speech_from_text_payload(
        payload=payload,
        audio_output_dir=audio_output_dir,
        settings=settings,
    )
    output_json_path.write_text(
        serialize_pipeline_speech_payload(speech_payload),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "pipelineJsonPath": str(pipeline_json_path),
                "outputJsonPath": str(output_json_path),
                "audioOutputDir": str(audio_output_dir),
                "segmentCount": len(speech_payload["narratedSegments"]),
                "provider": settings.provider_for_capability("tts"),
                "voice": speech_options.voice,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
