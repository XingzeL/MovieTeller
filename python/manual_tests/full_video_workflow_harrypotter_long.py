#!/usr/bin/env python3
"""
Run the full MovieTeller workflow for harrypotter_long.mp4.

Uses the current config stack:
- packaged default config
- config/local.yaml
- environment variables

Run from the repo root:

    python python/manual_tests/full_video_workflow_harrypotter_long.py

Behavior:
1. Run narration/polish first and persist text JSON immediately.
2. Then try TTS + embed video.

If TTS fails, the text JSON is still preserved on disk.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path


VIDEO_PATH = "test_artifacts/harrypotter_long.mp4"
OUTPUT_ROOT = "test_artifacts/harrypotter_long_manual_05160020"
ENABLE_SPEECH_AND_VIDEO = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_paths() -> None:
    root = _repo_root()
    for sub in (
        root / "python" / "movieteller_config" / "src",
        root / "python" / "pipeline_types" / "src",
        root / "python" / "media_utils" / "src",
        root / "python" / "subtitle_extraction" / "src",
        root / "python" / "subtitle_context" / "src",
        root / "python" / "video_frame_pool" / "src",
        root / "python" / "frame_source" / "src",
        root / "python" / "model_gateway" / "src",
        root / "python" / "narration" / "src",
        root / "python" / "narration_polish" / "src",
        root / "python" / "narration_speech" / "src",
        root / "python" / "narration_video" / "src",
        root / "python" / "movie_pipeline" / "src",
        root / "python" / "rerank" / "src",
    ):
        if sub.is_dir():
            sys.path.insert(0, str(sub))


def _slug_millis(value: float) -> str:
    return f"{int(round(float(value) * 1000.0)):08d}"


def _load_existing_payload(text_json_path: Path) -> dict[str, object] | None:
    if not text_json_path.is_file():
        return None
    payload = json.loads(text_json_path.read_text(encoding="utf-8"))
    narrated_segments = payload.get("narratedSegments")
    if not isinstance(narrated_segments, list) or not narrated_segments:
        raise ValueError(f"Existing text JSON has no narratedSegments: {text_json_path}")
    return payload


def _synthesize_speech_from_payload(
    *,
    payload: dict[str, object],
    audio_output_dir: Path,
    settings,
) -> dict[str, object]:
    from narration_speech import synthesize_narration_text

    narrated_segments = payload.get("narratedSegments")
    if not isinstance(narrated_segments, list) or not narrated_segments:
        raise ValueError("No narratedSegments found in payload")

    speech_options = settings.narration_speech_options()
    audio_output_dir.mkdir(parents=True, exist_ok=True)

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

        polish_payload = seg.get("polish")
        target_duration_sec = duration_sec
        if isinstance(polish_payload, dict) and polish_payload.get("targetDurationSec") is not None:
            target_duration_sec = float(polish_payload["targetDurationSec"])

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
    return payload


def _render_video_from_payload(
    *,
    payload: dict[str, object],
    video_path: Path,
    output_path: Path,
    settings,
) -> dict[str, object]:
    from narration_video import render_narrated_video
    from pipeline_types import NarrationAudioSegment

    narrated_segments = payload.get("narratedSegments")
    if not isinstance(narrated_segments, list) or not narrated_segments:
        raise ValueError("No narratedSegments found in payload")

    audio_segments: list[NarrationAudioSegment] = []
    for index, seg in enumerate(narrated_segments, start=1):
        if not isinstance(seg, dict):
            raise TypeError(f"Segment #{index} is not an object")
        speech = seg.get("speech")
        if not isinstance(speech, dict):
            raise ValueError(f"Segment #{index} has no synthesized speech payload")
        audio_path = str(speech.get("audioPath") or "").strip()
        if not audio_path:
            raise ValueError(f"Segment #{index} has empty speech audioPath")
        audio_segments.append(
            NarrationAudioSegment(
                start_sec=float(seg["startSec"]),
                end_sec=float(seg["endSec"]),
                audio_path=audio_path,
            )
        )

    render_result = render_narrated_video(
        str(video_path),
        audio_segments,
        output_path=str(output_path),
        options=settings.narration_video_options(),
        settings=settings,
    )
    payload["renderedVideo"] = {
        "videoPath": str(render_result.video_path),
        "outputPath": str(render_result.output_path),
        "segmentCount": int(render_result.segment_count),
        "videoDurationSec": float(render_result.video_duration_sec),
        "backgroundAudioVolume": float(render_result.background_audio_volume),
        "speechAudioVolume": float(render_result.speech_audio_volume),
        "timingRenderSec": (
            float(render_result.timing_render_sec)
            if render_result.timing_render_sec is not None
            else None
        ),
    }
    return payload


def main() -> int:
    _ensure_paths()

    from movie_pipeline.full_workflow import run_full_workflow, workflow_options_from_settings
    from movieteller_config import load_settings

    root = _repo_root()
    video_path = (root / VIDEO_PATH).resolve()
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        return 1

    output_root = (root / OUTPUT_ROOT).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    settings = load_settings(require_narration=True)
    base = workflow_options_from_settings(settings, output_root=str(output_root))
    movie = base.movie_pipeline_options
    if movie is None:
        raise RuntimeError("movie_pipeline_options missing")

    stem = video_path.stem
    text_json_path = output_root / f"{stem}.manual.pipeline.json"
    text_only_options = replace(
        base,
        enable_speech=False,
        enable_embed_video=False,
        movie_pipeline_options=replace(
            movie,
            speech_output_dir=None,
            embed_video=False,
            embed_output_path=None,
            speech_options=None,
            video_options=None,
        ),
    )
    text_payload = _load_existing_payload(text_json_path)
    if text_payload is None:
        text_payload = run_full_workflow(
            video_path=str(video_path),
            options=text_only_options,
            settings=settings,
        )
        text_json_path.write_text(
            json.dumps(text_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if not ENABLE_SPEECH_AND_VIDEO:
        print(
            json.dumps(
                {
                    "video": str(video_path),
                    "outputRoot": str(output_root),
                    "textJsonPath": str(text_json_path),
                    "narratedSegments": len(text_payload.get("narratedSegments", [])),
                    "speechAttempted": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        payload = json.loads(json.dumps(text_payload, ensure_ascii=False))
        payload = _synthesize_speech_from_payload(
            payload=payload,
            audio_output_dir=output_root / f"{stem}.narration_audio",
            settings=settings,
        )
        payload = _render_video_from_payload(
            payload=payload,
            video_path=video_path,
            output_path=output_root / f"{stem}.narrated.mp4",
            settings=settings,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "video": str(video_path),
                    "outputRoot": str(output_root),
                    "textJsonPath": str(text_json_path),
                    "narratedSegments": len(text_payload.get("narratedSegments", [])),
                    "speechAttempted": True,
                    "speechSucceeded": False,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    speech_json_path = output_root / f"{stem}.manual.pipeline.speech_video.json"
    speech_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "video": str(video_path),
                "outputRoot": str(output_root),
                "textJsonPath": str(text_json_path),
                "speechJsonPath": str(speech_json_path),
                "audioDir": str(output_root / f"{stem}.narration_audio"),
                "videoOutput": str(output_root / f"{stem}.narrated.mp4"),
                "narratedSegments": len(payload.get("narratedSegments", [])),
                "speechAttempted": True,
                "speechSucceeded": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
