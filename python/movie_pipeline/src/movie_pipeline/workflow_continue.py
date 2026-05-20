"""Continue workflow from an on-disk text pipeline JSON (TTS + optional render)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from narration_video import render_narrated_video
from narration_speech import synthesize_narration_text
from pipeline_types import NarrationAudioSegment


def deep_copy_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """JSON round-trip copy for isolating mutations from cached text payload."""
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _slug_millis(value: float) -> str:
    return f"{int(round(float(value) * 1000.0)):08d}"


def synthesize_speech_from_text_payload(
    *,
    payload: Mapping[str, Any],
    audio_output_dir: Path,
    settings: Any,
) -> dict[str, Any]:
    """Deep-copy payload then add ``speech`` per segment and ``speechOutputDir``."""
    out = deep_copy_payload(payload)
    narrated_segments = out.get("narratedSegments")
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

    out["speechOutputDir"] = str(audio_output_dir)
    return out


def render_video_from_narration_payload(
    *,
    payload: Mapping[str, Any],
    video_path: Path,
    output_path: Path,
    subtitle_srt_path: Path | None,
    settings: Any,
) -> dict[str, Any]:
    """Mix narration audio into video; set ``renderedVideo`` on a deep-copied payload."""
    out = deep_copy_payload(payload)
    narrated_segments = out.get("narratedSegments")
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
        subtitle_srt_path=(str(subtitle_srt_path) if subtitle_srt_path is not None else None),
        options=settings.narration_video_options(),
        settings=settings,
    )
    out["renderedVideo"] = {
        "videoPath": str(render_result.video_path),
        "outputPath": str(render_result.output_path),
        "segmentCount": int(render_result.segment_count),
        "videoDurationSec": float(render_result.video_duration_sec),
        "backgroundAudioVolume": float(render_result.background_audio_volume),
        "speechAudioVolume": float(render_result.speech_audio_volume),
        "subtitleSrtPath": render_result.subtitle_srt_path,
        "timingRenderSec": (
            float(render_result.timing_render_sec)
            if render_result.timing_render_sec is not None
            else None
        ),
    }
    return out

