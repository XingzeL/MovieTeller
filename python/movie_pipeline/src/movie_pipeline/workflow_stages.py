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

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from movie_pipeline.pipeline import run_pipeline_ctx
from movie_pipeline.runtime_context import RunContext
from movie_pipeline.types import ArtifactPaths, ResolvedExecutionConfig
from movie_pipeline.workflow_continue import render_video_from_narration_payload
from movieteller_config.schema import Settings
from subtitle_context import build_subtitle_context_index
from subtitle_context.index import subtitle_context_index_is_complete
from subtitle_extraction import extract_subtitles
from video_frame_pool import build_frame_pool


def stage_subtitle_extraction(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    resolved_settings: Settings,
) -> None:
    srt_path = Path(paths.srt_path)
    source_video = Path(paths.source_video)
    needs_extract = execution.force_rebuild_subtitles or not srt_path.is_file()
    if execution.extract_subtitles and needs_extract:
        so = execution.subtitle_extraction_options or resolved_settings.subtitle_extraction_options()
        extract_subtitles(
            str(source_video),
            videocaptioner_bin=so.videocaptioner_bin,
            output_srt_path=str(srt_path),
            asr=so.asr,
            language=so.language,
            timeout_sec=so.timeout_sec,
        )
    elif not srt_path.is_file():
        raise FileNotFoundError(
            f"Subtitle file not found and extraction disabled: {srt_path}"
        )


def stage_frame_pool(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    resolved_settings: Settings,
) -> None:
    manifest = Path(paths.frame_pool_manifest)
    needs_rebuild = execution.force_rebuild_frame_pool or not manifest.is_file()
    if execution.build_frame_pool and needs_rebuild:
        fo = execution.frame_pool_build_options or resolved_settings.frame_pool_build_options()
        build_frame_pool(
            video_path=paths.source_video,
            srt_path=paths.srt_path,
            output_dir=paths.frame_pool_dir,
            options=fo,
            settings=resolved_settings,
        )


def stage_subtitle_context(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
) -> str | None:
    subtitle_context_dir = Path(paths.subtitle_context_dir)
    if not execution.build_subtitle_context:
        return None
    needs_rebuild = (
        execution.force_rebuild_subtitle_context
        or not subtitle_context_index_is_complete(subtitle_context_dir)
    )
    if needs_rebuild:
        build_subtitle_context_index(
            srt_path=paths.srt_path,
            output_dir=str(subtitle_context_dir),
            options=execution.subtitle_context_build_options,
            settings=pipeline_settings,
        )
    return str(subtitle_context_dir)


def stage_narration_pipeline(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
    subtitle_context_index_dir: str | None,
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
    )


def stage_video_package(
    *,
    paths: ArtifactPaths,
    execution: ResolvedExecutionConfig,
    pipeline_settings: Settings,
    payload: dict[str, Any],
    video_renderer: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not execution.enable_embed_video:
        return payload
    output_path = (paths.embed_output_path or "").strip()
    if not output_path:
        raise ValueError("embed output path is required when enable_embed_video is True")
    return render_video_from_narration_payload(
        payload=payload,
        video_path=Path(paths.source_video),
        output_path=Path(output_path),
        subtitle_srt_path=None,
        settings=pipeline_settings,
        video_renderer=video_renderer,
    )
