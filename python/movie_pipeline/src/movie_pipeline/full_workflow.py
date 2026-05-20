from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from frame_source import FrameSourceOptions
from movie_pipeline.types import ArtifactPaths, FullWorkflowOptions, MoviePipelineOptions
from movie_pipeline.workflow_stages import (
    stage_frame_pool,
    stage_narration_pipeline,
    stage_subtitle_context,
    stage_subtitle_extraction,
    stage_video_package,
)
from movieteller_config import load_settings
from movieteller_config.schema import Settings


@dataclass(frozen=True)
class ProductRequest:
    level: str | None = None
    style: str | None = None
    cefr_level: str | None = None
    enable_speech: bool | None = None
    enable_embed_video: bool | None = None
    enable_subtitle_context: bool | None = None
    enable_polish: bool | None = None
    min_gap_sec: float | None = None
    subtitle_guard_sec: float | None = None
    force_rebuild_subtitles: bool | None = None
    force_rebuild_frame_pool: bool | None = None
    force_rebuild_subtitle_context: bool | None = None


def _coerce_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return None


def parse_product_request(payload: Mapping[str, Any] | None) -> ProductRequest:
    data = payload or {}
    force = data.get("forceRebuild")
    force_map = force if isinstance(force, Mapping) else {}
    return ProductRequest(
        level=(str(data["level"]).strip() if data.get("level") is not None else None),
        style=(str(data["style"]).strip() if data.get("style") is not None else None),
        cefr_level=(
            str(data["cefrLevel"]).strip() if data.get("cefrLevel") is not None else None
        ),
        enable_speech=_coerce_bool(data.get("enableSpeech")),
        enable_embed_video=_coerce_bool(data.get("enableEmbedVideo")),
        enable_subtitle_context=_coerce_bool(data.get("enableSubtitleContext")),
        enable_polish=_coerce_bool(data.get("enablePolish")),
        min_gap_sec=(float(data["minGapSec"]) if data.get("minGapSec") is not None else None),
        subtitle_guard_sec=(
            float(data["subtitleGuardSec"])
            if data.get("subtitleGuardSec") is not None
            else None
        ),
        force_rebuild_subtitles=_coerce_bool(force_map.get("subtitles")),
        force_rebuild_frame_pool=_coerce_bool(force_map.get("framePool")),
        force_rebuild_subtitle_context=_coerce_bool(force_map.get("subtitleContext")),
    )


def workflow_options_from_settings(
    settings: Settings,
    *,
    output_root: str | None = None,
) -> FullWorkflowOptions:
    return FullWorkflowOptions(
        output_root=output_root,
        subtitle_extraction_options=settings.subtitle_extraction_options(),
        frame_pool_build_options=settings.frame_pool_build_options(),
        subtitle_context_build_options=settings.subtitle_context_build_options(),
        movie_pipeline_options=MoviePipelineOptions(
            narration_options=settings.narration_options(),                             # 图生文旁白参数
            frame_source_options=FrameSourceOptions(                                    # 视频数据预处理帧池选项
                ffmpeg_bin=settings.ffmpeg_path,
                max_frames_per_segment=settings.max_frames_per_segment,
                max_edge_pixels=settings.narration_frame_max_edge,
                pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
            ),
            subtitle_context_build_options=settings.subtitle_context_build_options(),   # 台词信息RAG相关现象
            subtitle_context_retrieve_options=settings.subtitle_context_retrieve_options(),
            polish_options=(                                                            # 文生文润色选项
                settings.narration_polish_options()
                if settings.narration_polish_enabled
                else None
            ),
            speech_options=(                                                            # 语音生成选项
                settings.narration_speech_options()
                if settings.narration_tts_enabled
                else None
            ),
        ),
    )


def translate_product_request_to_workflow_options(
    request: ProductRequest,
    settings: Settings,
    *,
    output_root: str | None = None,
) -> FullWorkflowOptions:
    base = workflow_options_from_settings(settings, output_root=output_root)
    level = (request.level or "free").strip().lower()

    enable_subtitle_context = (
        request.enable_subtitle_context
        if request.enable_subtitle_context is not None
        else level in {"pro", "studio"}
    )
    enable_polish = (
        request.enable_polish
        if request.enable_polish is not None
        else level in {"pro", "studio"}
    )
    enable_speech = (
        request.enable_speech if request.enable_speech is not None else False
    )
    enable_embed_video = (
        request.enable_embed_video if request.enable_embed_video is not None else False
    )

    narration_options = settings.narration_options(prompt_style=request.style)
    movie_pipeline_options = MoviePipelineOptions(
        video_duration_sec=base.movie_pipeline_options.video_duration_sec
        if base.movie_pipeline_options is not None
        else None,
        min_gap_sec=(
            request.min_gap_sec
            if request.min_gap_sec is not None
            else (
                base.movie_pipeline_options.min_gap_sec
                if base.movie_pipeline_options is not None
                else 1.0
            )
        ),
        subtitle_guard_sec=(
            request.subtitle_guard_sec
            if request.subtitle_guard_sec is not None
            else (
                base.movie_pipeline_options.subtitle_guard_sec
                if base.movie_pipeline_options is not None
                else 0.25
            )
        ),
        ffprobe_bin=(
            base.movie_pipeline_options.ffprobe_bin
            if base.movie_pipeline_options is not None
            else "ffprobe"
        ),
        narration_options=narration_options,
        frame_source_options=(
            base.movie_pipeline_options.frame_source_options
            if base.movie_pipeline_options is not None
            else None
        ),
        subtitle_context_build_options=base.subtitle_context_build_options,
        subtitle_context_retrieve_options=(
            base.movie_pipeline_options.subtitle_context_retrieve_options
            if base.movie_pipeline_options is not None
            else None
        ),
        polish_options=(
            settings.narration_polish_options(
                prompt_style=narration_options.prompt_style,
                cefr_level=request.cefr_level,
            )
            if enable_polish
            else None
        ),
        speech_options=(
            settings.narration_speech_options()
            if enable_speech
            else None
        ),
        video_options=(
            settings.narration_video_options()
            if enable_embed_video
            else None
        ),
        embed_video=enable_embed_video,
    )

    return FullWorkflowOptions(
        extract_subtitles=True,
        build_frame_pool=True,
        build_subtitle_context=enable_subtitle_context,
        enable_polish=enable_polish,
        enable_speech=enable_speech,
        enable_embed_video=enable_embed_video,
        output_root=output_root,
        subtitle_extraction_options=base.subtitle_extraction_options,
        frame_pool_build_options=base.frame_pool_build_options,
        subtitle_context_build_options=base.subtitle_context_build_options,
        movie_pipeline_options=movie_pipeline_options,
    )


def run_full_workflow(
    *,
    video_path: str,
    options: FullWorkflowOptions | None = None,
    settings: Settings | None = None,
    narrator: Any = None,
    polisher: Any = None,
    synthesizer: Any = None,
    video_renderer: Any = None,
) -> dict[str, Any]:
    resolved_settings = settings if settings is not None else load_settings(require_narration=True)
    resolved_options = options or workflow_options_from_settings(resolved_settings)
    output_root = Path(
        resolved_options.output_root or Path(video_path).resolve().parent
    ).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    paths = ArtifactPaths.resolve(
        output_root=output_root,
        source_video=video_path,
        enable_speech=resolved_options.enable_speech,
        enable_embed_video=resolved_options.enable_embed_video,
    )

    stage_subtitle_extraction(
        paths=paths,
        resolved_options=resolved_options,
        resolved_settings=resolved_settings,
    )
    stage_frame_pool(
        paths=paths,
        resolved_options=resolved_options,
        resolved_settings=resolved_settings,
    )

    frame_pool_manifest = Path(paths.frame_pool_manifest)
    pipeline_settings = resolved_settings
    if frame_pool_manifest.is_file():
        manifest_value = str(frame_pool_manifest)
        if resolved_settings.frame_pool_manifest != manifest_value:
            pipeline_settings = replace(
                resolved_settings,
                frame_pool_manifest=manifest_value,
            )

    subtitle_context_index_dir = stage_subtitle_context(
        paths=paths,
        resolved_options=resolved_options,
        pipeline_settings=pipeline_settings,
    )

    base_pipeline_options = resolved_options.movie_pipeline_options or workflow_options_from_settings(
        pipeline_settings,
        output_root=str(output_root),
    ).movie_pipeline_options
    if base_pipeline_options is None:
        raise RuntimeError("movie_pipeline_options is required for full workflow")

    payload = stage_narration_pipeline(
        paths=paths,
        resolved_options=resolved_options,
        pipeline_settings=pipeline_settings,
        base_pipeline_options=base_pipeline_options,
        subtitle_context_index_dir=subtitle_context_index_dir,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
    )
    payload = stage_video_package(
        paths=paths,
        resolved_options=resolved_options,
        pipeline_settings=pipeline_settings,
        payload=payload,
        video_renderer=video_renderer,
    )
    payload["workflowArtifacts"] = {
        "videoPath": paths.source_video,
        "srtPath": paths.srt_path,
        "framePoolManifest": (
            paths.frame_pool_manifest if frame_pool_manifest.is_file() else None
        ),
        "subtitleContextIndexDir": subtitle_context_index_dir,
        "outputRoot": str(output_root),
    }
    return payload
