"""Five-stage full-workflow orchestration: fixed filenames and resume-by-artifact.

Stages (product order; see :func:`run_full_workflow`):

1. **subtitle_extraction** — ``{stem}.extracted.srt``
2. **frame_pool** — ``{stem}.frame_pool/manifest.jsonl``
3. **subtitle_context** — ``{stem}.subtitle_context`` (optional)
4. **narration_pipeline** — analysis + narration (+ optional TTS) via :func:`run_pipeline_ctx`
5. **video_package** — mux when ``enable_embed_video`` (runs inside stage 4 today)

**Resume:** each stage skips work when its primary artifact already exists and the
matching ``FullWorkflowOptions`` flag is true; disabling a stage still requires
prerequisite files to exist (same errors as before).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from movie_pipeline.pipeline import run_pipeline_ctx
from movie_pipeline.runtime_context import RunContext
from movie_pipeline.types import ArtifactPaths, FullWorkflowOptions, MoviePipelineOptions
from movieteller_config.schema import Settings
from subtitle_context import build_subtitle_context_index
from subtitle_context.index import subtitle_context_index_is_complete
from subtitle_extraction import extract_subtitles
from video_frame_pool import build_frame_pool


def stage_subtitle_extraction(
    *,
    paths: ArtifactPaths,
    resolved_options: FullWorkflowOptions,
    resolved_settings: Settings,
) -> None:
    srt_path = Path(paths.srt_path)
    source_video = Path(paths.source_video)
    if resolved_options.extract_subtitles and not srt_path.is_file():
        so = resolved_options.subtitle_extraction_options or resolved_settings.subtitle_extraction_options()
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
    resolved_options: FullWorkflowOptions,
    resolved_settings: Settings,
) -> None:
    manifest = Path(paths.frame_pool_manifest)
    if resolved_options.build_frame_pool and not manifest.is_file():
        fo = resolved_options.frame_pool_build_options or resolved_settings.frame_pool_build_options()
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
    resolved_options: FullWorkflowOptions,
    pipeline_settings: Settings,
) -> str | None:
    subtitle_context_dir = Path(paths.subtitle_context_dir)
    if not resolved_options.build_subtitle_context:
        return None
    if not subtitle_context_index_is_complete(subtitle_context_dir):
        build_subtitle_context_index(
            srt_path=paths.srt_path,
            output_dir=str(subtitle_context_dir),
            options=resolved_options.subtitle_context_build_options,
            settings=pipeline_settings,
        )
    return str(subtitle_context_dir)


def stage_narration_pipeline(
    *,
    paths: ArtifactPaths,
    resolved_options: FullWorkflowOptions,
    pipeline_settings: Settings,
    base_pipeline_options: MoviePipelineOptions,
    subtitle_context_index_dir: str | None,
    narrator: Callable[..., Any] | None = None,
    polisher: Callable[..., Any] | None = None,
    synthesizer: Callable[..., Any] | None = None,
    video_renderer: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    pipeline_options = replace(
        base_pipeline_options,
        subtitle_context_index_dir=subtitle_context_index_dir,
        build_subtitle_context=False,
        speech_output_dir=paths.speech_output_dir,
        embed_video=resolved_options.enable_embed_video,
        embed_output_path=paths.embed_output_path,
        polish_options=(
            base_pipeline_options.polish_options if resolved_options.enable_polish else None
        ),
        speech_options=(
            base_pipeline_options.speech_options if resolved_options.enable_speech else None
        ),
        video_options=(
            base_pipeline_options.video_options
            if resolved_options.enable_embed_video
            else None
        ),
    )
    ctx = RunContext(settings=pipeline_settings, pipeline=pipeline_options)
    return run_pipeline_ctx(
        srt_path=paths.srt_path,
        video_path=paths.source_video,
        ctx=ctx,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
        video_renderer=video_renderer,
    )
