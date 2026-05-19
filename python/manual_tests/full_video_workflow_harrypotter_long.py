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
2. Write a human-readable script (.manual.pipeline.script.txt) from that payload.
3. Merge extracted SRT + narrated segments into ``{stem}.final.subtitled.srt``, then remux
   ``{stem}.narration_softsubs.mp4`` with **mov_text** soft subtitles (no TTS; original audio kept).
4. When ``ENABLE_SPEECH_AND_VIDEO`` is True: TTS + full narrated video as before.

If TTS fails, the text JSON is still preserved on disk.

Routing comes from the shared gateway config. If text JSON already exists, the
script skips the second visual-understanding pass and continues from speech/video.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path


VIDEO_PATH = "test_artifacts/harrypotter_smoke1.mp4"
OUTPUT_ROOT = "test_artifacts/smoke2"
ENABLE_SPEECH_AND_VIDEO = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

#不安装多个本地包、又直接跑裸脚本**时，让解释器能找到分散在各 src 下的包
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
        root / "python" / "pipeline_transcript" / "src",
        root / "python" / "rerank" / "src",
    ):
        if sub.is_dir():
            sys.path.insert(0, str(sub))


def _slug_millis(value: float) -> str:
    return f"{int(round(float(value) * 1000.0)):08d}"

# 如果key长度小于等于6，则直接返回，否则返回前6个字符加上...
def _key_preview(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 6:
        return value
    return f"{value[:6]}..."

# 打印运行时调试信息
def _print_runtime_debug(settings) -> None:
    print(
        json.dumps(
            {
                "debug": {
                    "cwd": str(Path.cwd()),
                    "repoRoot": str(_repo_root()),
                    "env": {
                        "NEW_API_KEY_NARRATION_FREE_present": bool(os.environ.get("NEW_API_KEY_NARRATION_FREE")),
                        "TTS_API_KEY_present": bool(os.environ.get("TTS_API_KEY")),
                    },
                    "gateway": {
                        "defaultProvider": settings.default_provider(),
                        "ttsProvider": settings.provider_for_capability("tts"),
                    },
                    "apiProviders": dict(settings.api_providers),
                    "apiKeys": {
                        "newapi": _key_preview(settings.get_api_key("newapi")),
                        "dashscope": _key_preview(settings.get_api_key("dashscope")),
                    },
                    "modelDefaults": dict(settings.model_defaults),
                    "ttsVoice": settings.narration_speech_options().voice,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )

# 
def _write_readable_script_from_payload(
    payload: dict[str, object],
    output_path: Path,
    *,
    source_path: Path,
) -> None:
    """Write plain-text script (subtitle context + narration) via pipeline_transcript."""
    from pipeline_transcript import build_readable_script

    if not isinstance(payload.get("narratedSegments"), list) or not payload["narratedSegments"]:
        return
    body = build_readable_script(payload, source_path=source_path)
    output_path.write_text(body, encoding="utf-8")

# 试图找到已经存在的payload，如果存在则直接返回，否则运行全流程
# 返回的内容包含narratedSegments，narratedSegments是一个列表，列表中每个元素是一个字典，字典中包含startSec, endSec, speechText, polish等字段
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
    subtitle_srt_path: Path | None,
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
        subtitle_srt_path=(str(subtitle_srt_path) if subtitle_srt_path is not None else None),
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
        "subtitleSrtPath": render_result.subtitle_srt_path,
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
    _print_runtime_debug(settings)
    base = workflow_options_from_settings(settings, output_root=str(output_root)) #这里构造了一个全流程的配置结构，是从配置文件中构建；也可以自己构建
    movie = base.movie_pipeline_options
    if movie is None:
        raise RuntimeError("movie_pipeline_options missing")

# 获取视频文件名，用于生成文件名
    stem = video_path.stem
    text_json_path = output_root / f"{stem}.manual.pipeline.json"
    # 这里进行了一些参数的替换：替换了enable_speech和enable_embed_video为False，同时替换了movie_pipeline_options为None
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

    text_script_path = output_root / f"{stem}.manual.pipeline.script.txt"
    _write_readable_script_from_payload(
        text_payload,
        text_script_path,
        source_path=text_json_path,
    )

    if not ENABLE_SPEECH_AND_VIDEO:
        softsubs_video_path = output_root / f"{stem}.narration_softsubs.mp4"
        final_srt_path = output_root / f"{stem}.final.subtitled.srt"
        source_srt_path = output_root / f"{stem}.extracted.srt"
        subtitle_merge: dict[str, object] | None = None
        softsubs_error: str | None = None
        try:
            from narration_video import build_subtitled_narration_srt, render_video_with_soft_subtitles

            if not source_srt_path.is_file():
                raise FileNotFoundError(f"Missing extracted subtitles: {source_srt_path}")
            subtitle_result = build_subtitled_narration_srt(
                speech_video_json_path=str(text_json_path),
                source_srt_path=str(source_srt_path),
                output_srt_path=str(final_srt_path),
            )
            subtitle_merge = {
                "sourceSrtPath": subtitle_result.source_srt_path,
                "speechVideoJsonPath": subtitle_result.speech_video_json_path,
                "outputSrtPath": subtitle_result.output_srt_path,
                "insertedCueCount": subtitle_result.inserted_cue_count,
                "totalCueCount": subtitle_result.total_cue_count,
            }
            render_video_with_soft_subtitles(
                str(video_path),
                subtitle_srt_path=str(final_srt_path),
                output_path=str(softsubs_video_path),
                settings=settings,
            )
        except Exception as exc:
            softsubs_error = str(exc)

        summary: dict[str, object] = {
            "video": str(video_path),
            "outputRoot": str(output_root),
            "textJsonPath": str(text_json_path),
            "textScriptPath": str(text_script_path),
            "narratedSegments": len(text_payload.get("narratedSegments", [])),
            "speechAttempted": False,
            "extractedSrtPath": str(source_srt_path),
            "finalSubtitledSrtPath": str(final_srt_path),
            "softSubsVideoPath": str(softsubs_video_path),
        }
        if subtitle_merge is not None:
            summary["subtitleMerge"] = subtitle_merge
        if softsubs_error is not None:
            summary["softSubsError"] = softsubs_error
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    try:
        from narration_video import build_subtitled_narration_srt

        payload = json.loads(json.dumps(text_payload, ensure_ascii=False))
        payload = _synthesize_speech_from_payload(
            payload=payload,
            audio_output_dir=output_root / f"{stem}.narration_audio",
            settings=settings,
        )
        speech_json_path = output_root / f"{stem}.manual.pipeline.speech_video.json"
        speech_json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        source_srt_path = output_root / f"{stem}.extracted.srt"
        final_srt_path = output_root / f"{stem}.final.subtitled.srt"
        subtitle_result = build_subtitled_narration_srt(
            speech_video_json_path=str(speech_json_path),
            source_srt_path=str(source_srt_path),
            output_srt_path=str(final_srt_path),
        )
        payload["subtitleMerge"] = {
            "sourceSrtPath": subtitle_result.source_srt_path,
            "speechVideoJsonPath": subtitle_result.speech_video_json_path,
            "outputSrtPath": subtitle_result.output_srt_path,
            "insertedCueCount": subtitle_result.inserted_cue_count,
            "totalCueCount": subtitle_result.total_cue_count,
        }
        payload = _render_video_from_payload(
            payload=payload,
            video_path=video_path,
            output_path=output_root / f"{stem}.narrated.mp4",
            subtitle_srt_path=final_srt_path,
            settings=settings,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "video": str(video_path),
                    "outputRoot": str(output_root),
                    "textJsonPath": str(text_json_path),
                    "textScriptPath": str(text_script_path),
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

    speech_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    speech_video_script_path = output_root / f"{stem}.manual.pipeline.speech_video.script.txt"
    _write_readable_script_from_payload(
        payload,
        speech_video_script_path,
        source_path=speech_json_path,
    )

    print(
        json.dumps(
            {
                "video": str(video_path),
                "outputRoot": str(output_root),
                "textJsonPath": str(text_json_path),
                "textScriptPath": str(text_script_path),
                "speechJsonPath": str(speech_json_path),
                "speechVideoScriptPath": str(speech_video_script_path),
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
