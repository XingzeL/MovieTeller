"""Resolve ``WorkflowRequest`` + ``PolicyContext`` into ``ResolvedWorkflowConfig`` / ``ResolvedRunContext``."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from frame_source import FrameSourceOptions
from movieteller_config.schema import Settings

from movie_pipeline.types import (
    NarrationPipelineConfig,
    PolicyContext,
    ResolvedExecutionConfig,
    ResolvedRunContext,
    ResolvedWorkflowConfig,
    WorkflowRequest,
)


def pipeline_settings_with_resolved_frame_pool(
    resolved_settings: Settings,
    *,
    frame_pool_manifest_path: str,
) -> Settings:
    """Align :class:`Settings.frame_pool_manifest` with the on-disk workflow manifest.

    When the frame pool stage produced ``manifest.jsonl`` under the job output root,
    downstream pipeline stages should read frames from that path even if the global
    settings file still points elsewhere.
    """

    manifest = Path(frame_pool_manifest_path)
    if not manifest.is_file():
        return resolved_settings
    manifest_value = str(manifest)
    if resolved_settings.frame_pool_manifest == manifest_value:
        return resolved_settings
    return replace(resolved_settings, frame_pool_manifest=manifest_value)


def default_workflow_job_id(resolved_context: ResolvedRunContext, output_root: Path) -> str:
    request = resolved_context.request
    for value in (request.workspace_id, request.user_id, output_root.name):
        text = str(value or "").strip()
        if text:
            return text
    return output_root.name


def _base_workflow_options_from_settings(
    settings: Settings,
    *,
    output_root: str | None = None,
) -> ResolvedExecutionConfig:
    return ResolvedExecutionConfig(
        output_root=output_root,
        subtitle_extraction_options=settings.subtitle_extraction_options(),
        frame_pool_build_options=settings.frame_pool_build_options(),
        subtitle_context_build_options=settings.subtitle_context_build_options(),
        pipeline=NarrationPipelineConfig(
            narration_options=settings.narration_options(),
            frame_source_options=FrameSourceOptions(
                ffmpeg_bin=settings.ffmpeg_path,
                max_frames_per_segment=settings.max_frames_per_segment,
                max_edge_pixels=settings.narration_frame_max_edge,
                pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
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


def _merge_requested_flag(
    requested: bool | None,
    *,
    allowed: bool,
    default: bool | None,
) -> bool | None:
    if requested is not None:
        return bool(requested) and bool(allowed)
    return default


def _resolved_flag(
    requested: bool | None,
    *,
    allowed: bool,
    default: bool | None,
) -> bool:
    return bool(_merge_requested_flag(requested, allowed=allowed, default=default))


def _workflow_options_from_request(
    request: WorkflowRequest,
    settings: Settings,
    *,
    policy: PolicyContext,
) -> ResolvedExecutionConfig:
    output_root = request.output_root
    base = _base_workflow_options_from_settings(settings, output_root=output_root)

    enable_subtitle_context = _resolved_flag(
        request.enable_subtitle_context,
        allowed=policy.allow_subtitle_context,
        default=policy.default_enable_subtitle_context,
    )
    enable_polish = _resolved_flag(
        request.enable_polish,
        allowed=policy.allow_polish,
        default=policy.default_enable_polish,
    )
    enable_speech = _resolved_flag(
        request.enable_speech,
        allowed=policy.allow_speech,
        default=policy.default_enable_speech,
    )
    enable_embed_video = _resolved_flag(
        request.enable_embed_video,
        allowed=policy.allow_embed_video,
        default=policy.default_enable_embed_video,
    )

    subtitle_extraction_options = base.subtitle_extraction_options
    if request.source_language:
        subtitle_extraction_options = settings.subtitle_extraction_options(
            language=request.source_language
        )

    output_language = request.tts_language or request.narration_language or "en"
    tts_voice = request.tts_voice

    narration_options = settings.narration_options(
        prompt_style=request.prompt_style,
        output_language=output_language,
    )
    pipeline = NarrationPipelineConfig(
        video_duration_sec=base.pipeline.video_duration_sec,
        min_gap_sec=(
            request.min_gap_sec
            if request.min_gap_sec is not None
            else base.pipeline.min_gap_sec
        ),
        subtitle_guard_sec=(
            request.subtitle_guard_sec
            if request.subtitle_guard_sec is not None
            else base.pipeline.subtitle_guard_sec
        ),
        ffprobe_bin=base.pipeline.ffprobe_bin,
        narration_options=narration_options,
        frame_source_options=base.pipeline.frame_source_options,
        subtitle_context_build_options=base.subtitle_context_build_options,
        subtitle_context_retrieve_options=base.pipeline.subtitle_context_retrieve_options,
        polish_options=(
            settings.narration_polish_options(
                prompt_style=narration_options.prompt_style,
                cefr_level=request.cefr_level,
                output_language=output_language,
            )
            if enable_polish
            else None
        ),
        speech_options=(
            settings.narration_speech_options(voice=tts_voice)
            if enable_speech
            else None
        ),
        video_options=(
            settings.narration_video_options()
            if enable_embed_video
            else None
        ),
    )

    return ResolvedExecutionConfig(
        extract_subtitles=True,
        build_frame_pool=True,
        build_subtitle_context=enable_subtitle_context,
        force_rebuild_subtitles=bool(request.force_rebuild_subtitles),
        force_rebuild_frame_pool=bool(request.force_rebuild_frame_pool),
        force_rebuild_subtitle_context=bool(request.force_rebuild_subtitle_context),
        enable_polish=enable_polish,
        enable_speech=enable_speech,
        enable_embed_video=enable_embed_video,
        output_root=output_root,
        subtitle_extraction_options=subtitle_extraction_options,
        frame_pool_build_options=base.frame_pool_build_options,
        subtitle_context_build_options=base.subtitle_context_build_options,
        pipeline=pipeline,
    )


def default_policy_context_for_request(
    request: WorkflowRequest,
) -> PolicyContext:
    level = (request.user_tier or "").strip().lower() or None
    if level == "free":
        return PolicyContext(
            resolved_level="free",
            allow_subtitle_context=True,
            allow_polish=True,
            allow_speech=True,
            allow_embed_video=True,
            default_enable_subtitle_context=False,
            default_enable_polish=False,
            default_enable_speech=False,
            default_enable_embed_video=False,
        )
    if level in {"pro", "studio"}:
        return PolicyContext(
            resolved_level=level,
            allow_subtitle_context=True,
            allow_polish=True,
            allow_speech=True,
            allow_embed_video=True,
            default_enable_subtitle_context=True,
            default_enable_polish=True,
            default_enable_speech=False,
            default_enable_embed_video=False,
        )
    return PolicyContext(
        resolved_level=level,
        default_enable_subtitle_context=True,
        default_enable_polish=True,
    )


def _policy_adjusted_settings(
    settings: Settings,
    policy: PolicyContext,
) -> Settings:
    updated = settings
    if policy.default_provider_override:
        updated = replace(
            updated,
            gateway_default_provider=str(policy.default_provider_override).strip().lower(),
        )
    if policy.tts_provider_override is not None:
        tts_provider = str(policy.tts_provider_override).strip().lower()
        updated = replace(
            updated,
            gateway_tts_provider=tts_provider or None,
        )
    if policy.api_provider_overrides:
        merged = dict(updated.api_providers)
        merged.update({str(k): str(v) for k, v in policy.api_provider_overrides.items()})
        updated = replace(updated, api_providers=merged)
    if policy.api_key_overrides:
        merged = dict(updated.api_keys)
        merged.update({str(k): str(v) for k, v in policy.api_key_overrides.items()})
        updated = replace(updated, api_keys=merged)
    if policy.capability_model_overrides:
        merged = dict(updated.model_defaults)
        merged.update(
            {str(k).strip().lower(): str(v) for k, v in policy.capability_model_overrides.items()}
        )
        updated = replace(updated, model_defaults=merged)
    return updated


def resolve_workflow_config(
    *,
    request: WorkflowRequest,
    settings: Settings,
    policy: PolicyContext | None = None,
) -> ResolvedWorkflowConfig:
    resolved_policy = policy or default_policy_context_for_request(request)
    policy_settings = _policy_adjusted_settings(settings, resolved_policy)
    translated = _workflow_options_from_request(
        request,
        policy_settings,
        policy=resolved_policy,
    )
    if request.tts_voice:
        mpo = translated.pipeline
        speech_options = mpo.speech_options
        if speech_options is not None:
            translated = replace(
                translated,
                pipeline=replace(
                    mpo,
                    speech_options=replace(speech_options, voice=request.tts_voice),
                ),
            )
    return ResolvedWorkflowConfig(
        settings=policy_settings,
        request=request,
        policy=resolved_policy,
        execution=translated,
    )


def resolved_run_context_from_request(
    *,
    request: WorkflowRequest,
    settings: Settings,
    policy: PolicyContext | None = None,
) -> ResolvedRunContext:
    return ResolvedRunContext(
        config=resolve_workflow_config(request=request, settings=settings, policy=policy)
    )
