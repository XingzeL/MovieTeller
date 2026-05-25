"""Five-stage full-workflow orchestration: fixed filenames and resume-by-artifact.

Stages (product order; see :func:`run_full_workflow`):

1. **subtitle_extraction** — ``{stem}.extracted.srt``
2. **frame_pool** — ``{stem}.frame_pool/manifest.jsonl``
3. **subtitle_context** — ``{stem}.subtitle_context`` (optional)
4. **narration_pipeline** — analysis + narration (+ optional TTS) via :func:`run_pipeline_ctx`
5. **video_package** — mux when ``enable_embed_video``

**Resume:** each stage skips work when its primary artifact already exists and the
matching execution-config flag is true; disabling a stage still requires
prerequisite files to exist (same errors as before).
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events
from movie_pipeline.pipeline import run_pipeline_ctx
from movie_pipeline.resume_policy import (
    FramePoolPolicy,
    SubtitleContextPolicy,
    SubtitleExtractionPolicy,
    VideoPackagePolicy,
)
from movie_pipeline.runtime_context import RunContext
from movie_pipeline.types import ArtifactPaths, ResolvedExecutionConfig
from movie_pipeline.workflow_artifacts import (
    check_frame_pool_manifest,
    check_subtitle_context_index,
    check_subtitle_srt,
)
from movie_pipeline.workflow_continue import render_video_from_narration_payload
from movieteller_config.schema import Settings
from subtitle_context import build_subtitle_context_index
from subtitle_extraction import extract_subtitles
from video_frame_pool import build_frame_pool


def _emit_stage_failed(event: str, *, start: float, exc: Exception) -> None:
    emit_event(
        event,
        level=logging.ERROR,
        duration_ms=int((time.perf_counter() - start) * 1000),
        status="error",
        fatal=True,
        **classify_error(exc),
    )


def stage_subtitle_extraction(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    resolved_settings: Settings,
) -> None:
    start = time.perf_counter()
    emit_event(log_events.SUBTITLE_EXTRACTION_START, stage="subtitle_extraction")
    srt_path = Path(paths.srt_path)
    source_video = Path(paths.source_video)
    try:
        subtitle_check = check_subtitle_srt(srt_path)
        sub_policy = SubtitleExtractionPolicy.resolve(
            extract_subtitles=execution.extract_subtitles,
            force_rebuild_subtitles=execution.force_rebuild_subtitles,
            check=subtitle_check,
        )
        status = sub_policy.log_status
        if sub_policy.run_extract:
            so = execution.subtitle_extraction_options or resolved_settings.subtitle_extraction_options()
            extract_subtitles(
                str(source_video),
                videocaptioner_bin=so.videocaptioner_bin,
                output_srt_path=str(srt_path),
                asr=so.asr,
                language=so.language,
                timeout_sec=so.timeout_sec,
            )
        elif sub_policy.artifact_missing:
            raise FileNotFoundError(
                f"Reusable subtitle file not found and extraction disabled: {srt_path}"
            )
        emit_event(
            log_events.SUBTITLE_EXTRACTION_DONE,
            stage="subtitle_extraction",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status=status,
            x_srt_path=str(srt_path),
        )
    except Exception as exc:
        _emit_stage_failed(log_events.SUBTITLE_EXTRACTION_FAILED, start=start, exc=exc)
        raise


def stage_frame_pool(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    resolved_settings: Settings,
) -> None:
    start = time.perf_counter()
    emit_event(log_events.FRAME_POOL_START, stage="frame_pool")
    manifest = Path(paths.frame_pool_manifest)
    try:
        manifest_check = check_frame_pool_manifest(manifest)
        pool_policy = FramePoolPolicy.resolve(
            build_frame_pool=execution.build_frame_pool,
            force_rebuild_frame_pool=execution.force_rebuild_frame_pool,
            check=manifest_check,
        )
        status = pool_policy.log_status
        if pool_policy.run_build:
            fo = execution.frame_pool_build_options or resolved_settings.frame_pool_build_options()
            build_frame_pool(
                video_path=paths.source_video,
                srt_path=paths.srt_path,
                output_dir=paths.frame_pool_dir,
                options=fo,
                settings=resolved_settings,
            )
        emit_event(
            log_events.FRAME_POOL_DONE,
            stage="frame_pool",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status=status,
            x_manifest_path=str(manifest),
        )
    except Exception as exc:
        _emit_stage_failed(log_events.FRAME_POOL_FAILED, start=start, exc=exc)
        raise


def stage_subtitle_context(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
) -> str | None:
    start = time.perf_counter()
    emit_event(log_events.SUBTITLE_CONTEXT_START, stage="subtitle_context")
    subtitle_context_dir = Path(paths.subtitle_context_dir)
    try:
        if not execution.build_subtitle_context:
            emit_event(
                log_events.SUBTITLE_CONTEXT_DONE,
                stage="subtitle_context",
                duration_ms=int((time.perf_counter() - start) * 1000),
                status="skipped",
            )
            return None
        context_check = check_subtitle_context_index(subtitle_context_dir)
        ctx_policy = SubtitleContextPolicy.resolve(
            force_rebuild_subtitle_context=execution.force_rebuild_subtitle_context,
            check=context_check,
        )
        status = ctx_policy.log_status
        if ctx_policy.run_build:
            build_subtitle_context_index(
                srt_path=paths.srt_path,
                output_dir=str(subtitle_context_dir),
                options=execution.subtitle_context_build_options,
                settings=pipeline_settings,
            )
        emit_event(
            log_events.SUBTITLE_CONTEXT_DONE,
            stage="subtitle_context",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status=status,
            x_index_dir=str(subtitle_context_dir),
        )
        return str(subtitle_context_dir)
    except Exception as exc:
        _emit_stage_failed(log_events.SUBTITLE_CONTEXT_FAILED, start=start, exc=exc)
        raise


def stage_narration_pipeline(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
    subtitle_context_index_dir: str | None,
    job_id: str | None = None,
    narrator: Callable[..., Any] | None = None,
    polisher: Callable[..., Any] | None = None,
    synthesizer: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    pipeline_config = replace(
        execution.pipeline,
        polish_options=(
            execution.pipeline.polish_options if execution.enable_polish else None
        ),
        speech_options=(
            execution.pipeline.speech_options if execution.enable_speech else None
        ),
        video_options=(
            execution.pipeline.video_options
            if execution.enable_embed_video
            else None
        ),
    )
    ctx = RunContext(settings=pipeline_settings, pipeline=pipeline_config)
    return run_pipeline_ctx(
        srt_path=paths.srt_path,
        video_path=paths.source_video,
        ctx=ctx,
        subtitle_context_index_dir=subtitle_context_index_dir,
        build_subtitle_context=False,
        speech_output_dir=paths.speech_output_dir,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
        job_id=job_id,
    )


def stage_video_package(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
    payload: dict[str, Any],
    video_renderer: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    emit_event(log_events.VIDEO_PACKAGE_START, stage="video_package")
    try:
        video_policy = VideoPackagePolicy.resolve(
            enable_embed_video=execution.enable_embed_video,
        )
        if not video_policy.run_render:
            emit_event(
                log_events.VIDEO_PACKAGE_DONE,
                stage="video_package",
                duration_ms=int((time.perf_counter() - start) * 1000),
                status=video_policy.log_status,
            )
            return payload
        output_path = (paths.embed_output_path or "").strip()
        if not output_path:
            raise ValueError("embed output path is required when enable_embed_video is True")
        out = render_video_from_narration_payload(
            payload=payload,
            video_path=Path(paths.source_video),
            output_path=Path(output_path),
            subtitle_srt_path=None,
            settings=pipeline_settings,
            video_renderer=video_renderer,
        )
        emit_event(
            log_events.VIDEO_PACKAGE_DONE,
            stage="video_package",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status=video_policy.log_status,
            x_video_output_path=output_path,
        )
        return out
    except Exception as exc:
        _emit_stage_failed(log_events.VIDEO_PACKAGE_FAILED, start=start, exc=exc)
        raise
