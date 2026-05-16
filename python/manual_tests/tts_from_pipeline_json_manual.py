#!/usr/bin/env python3
"""
Generate TTS audio only from an existing MovieTeller pipeline JSON.

Edit ``PIPELINE_JSON_PATH`` below, then run:

    python python/manual_tests/tts_from_pipeline_json_manual.py

This script does not rerun subtitle extraction, frame pooling, subtitle context,
or narration. It only reads ``narratedSegments`` from an existing JSON file and
generates speech audio for each segment using the shared TTS capability config.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Existing pipeline JSON with narratedSegments.
PIPELINE_JSON_PATH = "test_artifacts/harrypotter_long/harrypotter_long.manual.pipeline.json"

# Output directory for generated audio. If None, defaults to:
# <pipeline_json_dir>/<video_stem>.narration_audio
AUDIO_OUTPUT_DIR: str | None = None

# Output JSON path after speech is attached. If None, defaults to:
# <pipeline_json_dir>/<pipeline_json_stem>.speech_only.json
OUTPUT_JSON_PATH: str | None = None

# If False, reuse already generated audio files when present.
OVERWRITE_AUDIO = False


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


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _slug_millis(value: float) -> str:
    return f"{int(round(float(value) * 1000.0)):08d}"


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

    from movieteller_config import load_settings
    from narration_speech import synthesize_narration_text

    root = _repo_root()
    pipeline_json_path = (root / PIPELINE_JSON_PATH).resolve()
    if not pipeline_json_path.is_file():
        print(f"Pipeline JSON not found: {pipeline_json_path}", file=sys.stderr)
        return 1

    payload = json.loads(pipeline_json_path.read_text(encoding="utf-8"))
    narrated_segments = payload.get("narratedSegments")
    if not isinstance(narrated_segments, list) or not narrated_segments:
        print("No narratedSegments found in pipeline JSON", file=sys.stderr)
        return 1

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
        else pipeline_json_path.with_name(f"{pipeline_json_path.stem}.speech_only.json")
    )

    for index, seg in enumerate(narrated_segments, start=1):
        if not isinstance(seg, dict):
            raise TypeError(f"Segment #{index} is not an object")
        start_sec = float(seg["startSec"])
        end_sec = float(seg["endSec"])
        duration_sec = float(seg.get("durationSec") or (end_sec - start_sec))
        speech_text = str(seg.get("speechText") or seg.get("text") or "").strip()
        if not speech_text:
            raise ValueError(f"Segment #{index} has empty speech text")

        slug = f"segment_{index:03d}_{_slug_millis(start_sec)}_{_slug_millis(end_sec)}"
        audio_path = audio_output_dir / f"{slug}.mp3"
        metadata_path = audio_output_dir / f"{slug}.mp3.jsonl"

        if audio_path.is_file() and metadata_path.is_file() and not OVERWRITE_AUDIO:
            _log(f"[{index}/{len(narrated_segments)}] reusing audio -> {audio_path.name}")
            speech_payload = seg.get("speech")
            if not isinstance(speech_payload, dict):
                speech_payload = {
                    "text": speech_text,
                    "audioPath": str(audio_path),
                    "metadataPath": str(metadata_path),
                    "segmentDurationSec": duration_sec,
                    "targetDurationSec": duration_sec,
                    "rawDurationSec": duration_sec,
                    "audioDurationSec": duration_sec,
                    "durationDeltaSec": 0.0,
                    "provider": speech_options.provider_slug,
                    "voice": speech_options.voice,
                    "rate": speech_options.rate,
                    "volume": speech_options.volume,
                    "pitch": speech_options.pitch,
                    "boundary": speech_options.boundary,
                    "fitApplied": False,
                    "fitsDuration": True,
                    "timingTtsSec": None,
                    "timingFitSec": None,
                }
            seg["speech"] = speech_payload
            continue

        polish_payload = seg.get("polish")
        target_duration_sec = duration_sec
        if isinstance(polish_payload, dict) and polish_payload.get("targetDurationSec") is not None:
            target_duration_sec = float(polish_payload["targetDurationSec"])

        _log(f"[{index}/{len(narrated_segments)}] synthesizing -> {audio_path.name}")
        result = synthesize_narration_text(
            speech_text,
            duration_sec,
            output_path=str(audio_path),
            metadata_path=str(metadata_path),
            target_duration_sec=target_duration_sec,
            options=speech_options,
            settings=settings,
        )
        seg["speech"] = {
            "text": result.text,
            "audioPath": result.audio_path,
            "metadataPath": result.metadata_path,
            "segmentDurationSec": result.segment_duration_sec,
            "targetDurationSec": result.target_duration_sec,
            "rawDurationSec": result.raw_duration_sec,
            "audioDurationSec": result.audio_duration_sec,
            "durationDeltaSec": result.duration_delta_sec,
            "fitsDuration": result.fits_duration,
            "provider": result.provider,
            "voice": result.voice,
            "rate": result.rate,
            "volume": result.volume,
            "pitch": result.pitch,
            "boundary": result.boundary,
            "fitApplied": result.fit_applied,
            "timingTtsSec": result.timing_tts_sec,
            "timingFitSec": result.timing_fit_sec,
        }

    payload["speechOutputDir"] = str(audio_output_dir)
    output_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "pipelineJsonPath": str(pipeline_json_path),
                "outputJsonPath": str(output_json_path),
                "audioOutputDir": str(audio_output_dir),
                "segmentCount": len(narrated_segments),
                "provider": speech_options.provider_slug,
                "voice": speech_options.voice,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
