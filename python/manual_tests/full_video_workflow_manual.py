#!/usr/bin/env python3
"""
Run the full MovieTeller workflow for one video with editable constants.

Edit ``VIDEO_PATH`` below, then run from the repo root or anywhere:

    python python/manual_tests/full_video_workflow_manual.py

This script is intentionally thin:
1. Load shared settings.
2. Build a frontend-style ``WorkflowRequest``.
3. Resolve it into ``ResolvedRunContext``.
4. Execute ``run_full_workflow(resolved_context=...)``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


VIDEO_PATH = "test_artifacts/harrypotter2.mp4"
OUTPUT_ROOT = "test_artifacts"

FORCE_EXTRACT_SUBTITLES = False
FORCE_BUILD_FRAME_POOL = False
FORCE_BUILD_SUBTITLE_CONTEXT = False

ENABLE_SUBTITLE_CONTEXT = True
ENABLE_POLISH = True
ENABLE_SPEECH = False
ENABLE_EMBED_VIDEO = False

MIN_GAP_SEC = 1.0
SUBTITLE_GUARD_SEC = 0.25


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


def main() -> int:
    _ensure_paths()

    from movie_pipeline import (
        WorkflowRequest,
        resolved_run_context_from_request,
        run_full_workflow,
        serialize_pipeline_render_payload,
        serialize_pipeline_speech_payload,
        serialize_pipeline_text_payload,
    )
    from movieteller_config import load_settings

    root = _repo_root()
    video_path = (root / VIDEO_PATH).resolve()
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        return 1

    output_root = (root / OUTPUT_ROOT).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem

    settings = load_settings(require_narration=True)
    request = WorkflowRequest(
        video_path=str(video_path),
        output_root=str(output_root),
        min_gap_sec=MIN_GAP_SEC,
        subtitle_guard_sec=SUBTITLE_GUARD_SEC,
        enable_subtitle_context=ENABLE_SUBTITLE_CONTEXT,
        enable_polish=ENABLE_POLISH,
        enable_speech=ENABLE_SPEECH,
        enable_embed_video=ENABLE_EMBED_VIDEO,
        force_rebuild_subtitles=FORCE_EXTRACT_SUBTITLES,
        force_rebuild_frame_pool=FORCE_BUILD_FRAME_POOL,
        force_rebuild_subtitle_context=FORCE_BUILD_SUBTITLE_CONTEXT,
    )
    resolved_context = resolved_run_context_from_request(
        request=request,
        settings=settings,
    )
    payload = run_full_workflow(
        resolved_context=resolved_context,
    )

    text_json_path = output_root / f"{stem}.manual.pipeline.text.json"
    speech_json_path = output_root / f"{stem}.manual.pipeline.speech.json"
    render_json_path = output_root / f"{stem}.manual.pipeline.render.json"

    if "renderedVideo" in payload:
        render_json_path.write_text(
            serialize_pipeline_render_payload(payload),
            encoding="utf-8",
        )
        payload_json_path = render_json_path
    elif any(
        isinstance(seg, dict) and isinstance(seg.get("speech"), dict)
        for seg in payload.get("narratedSegments", [])
    ):
        speech_json_path.write_text(
            serialize_pipeline_speech_payload(payload),
            encoding="utf-8",
        )
        payload_json_path = speech_json_path
    else:
        text_json_path.write_text(
            serialize_pipeline_text_payload(payload),
            encoding="utf-8",
        )
        payload_json_path = text_json_path

    print(
        json.dumps(
            {
                "video": str(video_path),
                "outputRoot": str(output_root),
                "payloadJsonPath": str(payload_json_path),
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
