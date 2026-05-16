#!/usr/bin/env python3
"""
Run the full local MovieTeller workflow for one video with editable constants.

Edit ``VIDEO_PATH`` below, then run from the repo root or anywhere:

    python python/manual_tests/full_video_workflow_manual.py

Workflow:
1. subtitle_extraction
2. video_frame_pool build
3. subtitle_context build
4. movie_pipeline narration + optional polish/speech/render

Model/provider routing is read from the shared gateway-oriented config stack
(`gateway.default_provider`, `api_providers`, `api_keys`, `model_defaults`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Edit this to the video you want to process. Relative paths are resolved from
# the repository root.
VIDEO_PATH = "test_artifacts/harrypotter2.mp4"

# All generated outputs are written here:
# - <stem>.extracted.srt
# - <stem>.frame_pool/
# - <stem>.subtitle_context/
# - <stem>.manual.pipeline.json
# - optional speech/video outputs
OUTPUT_ROOT = "test_artifacts"

# Force rebuilding steps even if artifacts already exist.
FORCE_EXTRACT_SUBTITLES = False
FORCE_BUILD_FRAME_POOL = False
FORCE_BUILD_SUBTITLE_CONTEXT = False

# Feature toggles for the later pipeline stages.
ENABLE_SUBTITLE_CONTEXT = True
ENABLE_POLISH = True
ENABLE_SPEECH = False
ENABLE_EMBED_VIDEO = False

# Narration candidate filtering.
MIN_GAP_SEC = 1.0
SUBTITLE_GUARD_SEC = 0.25
MAX_CANDIDATES: int | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_paths() -> None:
    root = _repo_root()
    for sub in (
        root / "python" / "movieteller_config" / "src",
        root / "python" / "pipeline_types" / "src",
        root / "python" / "media_utils" / "src",
        root / "python" / "subtitle_extraction" / "src",
        root / "python" / "subtitle_analysis" / "src",
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


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def main() -> int:
    _ensure_paths()

    from frame_source import FrameSourceOptions
    from movie_pipeline import MoviePipelineOptions, run_pipeline
    from movieteller_config import load_flat_dict
    from movieteller_config.schema import settings_from_dict
    from subtitle_context import build_subtitle_context_index
    from subtitle_context.index import subtitle_context_index_is_complete
    from subtitle_extraction import extract_subtitles
    from video_frame_pool import build_frame_pool

    root = _repo_root()
    video_path = (root / VIDEO_PATH).resolve()
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        return 1

    output_root = (root / OUTPUT_ROOT).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem

    srt_path = output_root / f"{stem}.extracted.srt"
    frame_pool_dir = output_root / f"{stem}.frame_pool"
    frame_pool_manifest = frame_pool_dir / "manifest.jsonl"
    subtitle_context_dir = output_root / f"{stem}.subtitle_context"
    pipeline_json_path = output_root / f"{stem}.manual.pipeline.json"
    speech_output_dir = output_root / f"{stem}.narration_audio"
    embed_output_path = output_root / f"{stem}.narrated.mp4"

    base_flat = load_flat_dict()
    if frame_pool_manifest.exists():
        base_flat["frame_pool_manifest"] = str(frame_pool_manifest)
    settings = settings_from_dict(base_flat)

    if FORCE_EXTRACT_SUBTITLES or not srt_path.is_file():
        _log(f"[1/4] extracting subtitles -> {srt_path}")
        extract_subtitles(
            str(video_path),
            videocaptioner_bin=settings.videocaptioner_bin,
            output_srt_path=str(srt_path),
            asr=settings.videocaptioner_asr,
            language=settings.videocaptioner_language,
            timeout_sec=(
                None
                if settings.videocaptioner_transcribe_timeout_ms is None
                else max(1.0, float(settings.videocaptioner_transcribe_timeout_ms) / 1000.0)
            ),
        )
    else:
        _log(f"[1/4] reusing subtitles -> {srt_path}")

    if FORCE_BUILD_FRAME_POOL or not frame_pool_manifest.is_file():
        _log(f"[2/4] building frame pool -> {frame_pool_dir}")
        build_frame_pool(
            video_path=str(video_path),
            srt_path=str(srt_path),
            output_dir=str(frame_pool_dir),
            settings=settings,
        )
    else:
        _log(f"[2/4] reusing frame pool -> {frame_pool_dir}")

    flat = load_flat_dict()
    flat["frame_pool_manifest"] = str(frame_pool_manifest)
    settings = settings_from_dict(flat)

    subtitle_context_index_dir: str | None = None
    if ENABLE_SUBTITLE_CONTEXT:
        if FORCE_BUILD_SUBTITLE_CONTEXT or not subtitle_context_index_is_complete(
            subtitle_context_dir
        ):
            _log(f"[3/4] building subtitle context -> {subtitle_context_dir}")
            build_subtitle_context_index(
                srt_path=str(srt_path),
                output_dir=str(subtitle_context_dir),
                settings=settings,
            )
        else:
            _log(f"[3/4] reusing subtitle context -> {subtitle_context_dir}")
        subtitle_context_index_dir = str(subtitle_context_dir)
    else:
        _log("[3/4] subtitle context disabled")

    _log(f"[4/4] running movie_pipeline -> {pipeline_json_path}")
    pipeline_options = MoviePipelineOptions(
        min_gap_sec=MIN_GAP_SEC,
        subtitle_guard_sec=SUBTITLE_GUARD_SEC,
        max_candidates=MAX_CANDIDATES,
        subtitle_context_index_dir=subtitle_context_index_dir,
        speech_output_dir=(str(speech_output_dir) if ENABLE_SPEECH else None),
        embed_video=ENABLE_EMBED_VIDEO,
        embed_output_path=(str(embed_output_path) if ENABLE_EMBED_VIDEO else None),
        narration_options=settings.narration_options(),
        frame_source_options=FrameSourceOptions(
            ffmpeg_bin=settings.ffmpeg_path,
            max_frames_per_segment=settings.max_frames_per_segment,
            max_edge_pixels=settings.narration_frame_max_edge,
            pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
            allow_uniform_fallback=True,
        ),
        subtitle_context_build_options=settings.subtitle_context_build_options(),
        subtitle_context_retrieve_options=settings.subtitle_context_retrieve_options(),
        polish_options=(settings.narration_polish_options() if ENABLE_POLISH else None),
        speech_options=(settings.narration_speech_options() if ENABLE_SPEECH else None),
        video_options=(settings.narration_video_options() if ENABLE_EMBED_VIDEO else None),
    )
    payload = run_pipeline(
        srt_path=str(srt_path),
        video_path=str(video_path),
        pipeline_options=pipeline_options,
        settings=settings,
    )
    pipeline_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "video": str(video_path),
                "srtPath": str(srt_path),
                "framePoolManifest": str(frame_pool_manifest),
                "subtitleContextIndexDir": subtitle_context_index_dir,
                "pipelineJsonPath": str(pipeline_json_path),
                "narratedSegments": len(payload.get("narratedSegments", [])),
                "speechEnabled": ENABLE_SPEECH,
                "embedVideoEnabled": ENABLE_EMBED_VIDEO,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
