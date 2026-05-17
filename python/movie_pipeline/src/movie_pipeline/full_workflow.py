from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from frame_source import FrameSourceOptions
from movie_pipeline.pipeline import run_pipeline
from movie_pipeline.types import FullWorkflowOptions, MoviePipelineOptions
from movieteller_config import load_settings
from movieteller_config.schema import Settings
from subtitle_context import build_subtitle_context_index
from subtitle_context.index import subtitle_context_index_is_complete
from subtitle_extraction import extract_subtitles
from video_frame_pool import build_frame_pool


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
            polish_options=(
                settings.narration_polish_options()
                if settings.narration_polish_enabled
                else None
            ),
            speech_options=(
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
) -> dict[str, Any]:
    resolved_settings = settings if settings is not None else load_settings(require_narration=True)
    resolved_options = options or workflow_options_from_settings(resolved_settings)
    output_root = Path(
        resolved_options.output_root or Path(video_path).resolve().parent
    ).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    source_video = Path(video_path).resolve()
    stem = source_video.stem
    srt_path = output_root / f"{stem}.extracted.srt"
    frame_pool_dir = output_root / f"{stem}.frame_pool"
    frame_pool_manifest = frame_pool_dir / "manifest.jsonl"
    subtitle_context_dir = output_root / f"{stem}.subtitle_context"

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
        raise FileNotFoundError(f"Subtitle file not found and extraction disabled: {srt_path}")

    if resolved_options.build_frame_pool and not frame_pool_manifest.is_file():
        fo = resolved_options.frame_pool_build_options or resolved_settings.frame_pool_build_options()
        build_frame_pool(
            video_path=str(source_video),
            srt_path=str(srt_path),
            output_dir=str(frame_pool_dir),
            options=fo,
            settings=resolved_settings,
        )

    pipeline_settings = resolved_settings
    if frame_pool_manifest.is_file():
        manifest_value = str(frame_pool_manifest)
        if resolved_settings.frame_pool_manifest != manifest_value:
            pipeline_settings = replace(
                resolved_settings,
                frame_pool_manifest=manifest_value,
            )

    subtitle_context_index_dir: str | None = None
    if resolved_options.build_subtitle_context:
        if not subtitle_context_index_is_complete(subtitle_context_dir):
            build_subtitle_context_index(
                srt_path=str(srt_path),
                output_dir=str(subtitle_context_dir),
                options=resolved_options.subtitle_context_build_options,
                settings=pipeline_settings,
            )
        subtitle_context_index_dir = str(subtitle_context_dir)

    base_pipeline_options = resolved_options.movie_pipeline_options or workflow_options_from_settings(
        pipeline_settings,
        output_root=str(output_root),
    ).movie_pipeline_options
    if base_pipeline_options is None:
        raise RuntimeError("movie_pipeline_options is required for full workflow")

    speech_output_dir = (
        str(output_root / f"{stem}.narration_audio")
        if resolved_options.enable_speech
        else None
    )
    embed_output_path = (
        str(output_root / f"{stem}.narrated.mp4")
        if resolved_options.enable_embed_video
        else None
    )
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=base_pipeline_options.video_duration_sec,
        min_gap_sec=base_pipeline_options.min_gap_sec,
        subtitle_guard_sec=base_pipeline_options.subtitle_guard_sec,
        ffprobe_bin=base_pipeline_options.ffprobe_bin,
        subtitle_context_index_dir=subtitle_context_index_dir,
        build_subtitle_context=False,
        speech_output_dir=speech_output_dir,
        embed_video=resolved_options.enable_embed_video,
        embed_output_path=embed_output_path,
        narration_options=base_pipeline_options.narration_options,
        frame_source_options=base_pipeline_options.frame_source_options,
        subtitle_context_build_options=base_pipeline_options.subtitle_context_build_options,
        subtitle_context_retrieve_options=base_pipeline_options.subtitle_context_retrieve_options,
        polish_options=(
            base_pipeline_options.polish_options if resolved_options.enable_polish else None
        ),
        speech_options=(
            base_pipeline_options.speech_options if resolved_options.enable_speech else None
        ),
        video_options=(
            base_pipeline_options.video_options if resolved_options.enable_embed_video else None
        ),
    )
    payload = run_pipeline(
        srt_path=str(srt_path),
        video_path=str(source_video),
        pipeline_options=pipeline_options,
        settings=pipeline_settings,
    )
    payload["workflowArtifacts"] = {
        "videoPath": str(source_video),
        "srtPath": str(srt_path),
        "framePoolManifest": (str(frame_pool_manifest) if frame_pool_manifest.is_file() else None),
        "subtitleContextIndexDir": subtitle_context_index_dir,
        "outputRoot": str(output_root),
    }
    return payload
