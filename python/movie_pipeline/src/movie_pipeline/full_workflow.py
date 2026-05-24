from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path
from typing import Any

from frame_source import FrameSourceOptions
from movieteller_logging import (
    bind_pipeline_log_context,
    classify_error,
    configure_async_logging,
    emit_event,
    progress_from_jsonl,
    reset_pipeline_log_context,
    shutdown_async_logging,
)
from movieteller_logging import events as log_events
from movie_pipeline.types import (
    ArtifactPaths,
    NarrationPipelineConfig,
    PolicyContext,
    ResolvedExecutionConfig,
    ResolvedRunContext,
    ResolvedWorkflowConfig,
    WorkflowRequest,
)
from movie_pipeline.job import JobRecord, WorkflowArtifacts, write_job_record
from movie_pipeline.workflow_stages import (
    stage_frame_pool,
    stage_narration_pipeline,
    stage_subtitle_context,
    stage_subtitle_extraction,
    stage_video_package,
)
from movie_pipeline.workflow_exports import export_workflow_artifacts
from movieteller_config.schema import Settings


def _default_job_id(resolved_context: ResolvedRunContext, output_root: Path) -> str:
    request = resolved_context.request
    for value in (request.workspace_id, request.user_id, output_root.name):
        text = str(value or "").strip()
        if text:
            return text
    return output_root.name


def _configure_workflow_logging(
    *,
    settings: Settings,
    job_id: str,
) -> None:
    log_opts = settings.pipeline_logging_options()
    configure_async_logging(
        enabled=log_opts.enabled,
        level=log_opts.level,
        format=log_opts.format,
        stderr=log_opts.stderr,
        file=log_opts.file,
    )
    if log_opts.enabled:
        emit_event(log_events.WORKFLOW_LOGGING_CONFIGURED, job_id=job_id, status="ok")


def _workflow_log_path(settings: Settings) -> str | None:
    log_opts = settings.pipeline_logging_options()
    return log_opts.file if log_opts.enabled and log_opts.file else None


def _write_workflow_manifest(
    *,
    path: Path,
    status: str,
    job_id: str,
    input_video_path: str,
    output_root: Path,
    user_id: str | None,
    log_path: str | None,
    artifacts: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    progress = progress_from_jsonl(log_path).to_dict() if log_path else {}
    record = JobRecord(
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        input_video_path=str(input_video_path),
        output_root=str(output_root),
        user_id=user_id,
        current_stage=progress.get("current_stage"),
        progress=progress,
        error=error,
        artifacts=artifacts or {},
    )
    write_job_record(record, path)


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

    narration_options = settings.narration_options(prompt_style=request.prompt_style)
    pipeline = NarrationPipelineConfig(
        video_duration_sec=base.pipeline.video_duration_sec,
        min_gap_sec=(
            request.min_gap_sec
            if request.min_gap_sec is not None
            else (
                base.pipeline.min_gap_sec
            )
        ),
        subtitle_guard_sec=(
            request.subtitle_guard_sec
            if request.subtitle_guard_sec is not None
            else (
                base.pipeline.subtitle_guard_sec
            )
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
        subtitle_extraction_options=base.subtitle_extraction_options,
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
    return PolicyContext(resolved_level=level)


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


def run_full_workflow(
    *,
    resolved_context: ResolvedRunContext,
    narrator: Any = None,
    polisher: Any = None,
    synthesizer: Any = None,
    video_renderer: Any = None,
) -> dict[str, Any]:
    resolved_settings = resolved_context.settings
    resolved_execution = resolved_context.execution
    resolved_video_path = resolved_context.video_path
    output_root = Path(
        resolved_execution.output_root or Path(resolved_video_path).resolve().parent
    ).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    job_id = _default_job_id(resolved_context, output_root)
    _configure_workflow_logging(settings=resolved_settings, job_id=job_id)
    workflow_json_path = output_root / "workflow.json"
    workflow_log_path = _workflow_log_path(resolved_settings)
    log_token = bind_pipeline_log_context(
        job_id=job_id,
        stage="workflow",
        x_video_path=str(resolved_video_path),
        x_output_root=str(output_root),
    )

    try:
        emit_event(log_events.WORKFLOW_START, status="ok")
        paths = ArtifactPaths.resolve(
            output_root=output_root,
            source_video=resolved_video_path,
            enable_speech=resolved_execution.enable_speech,
            enable_embed_video=resolved_execution.enable_embed_video,
        )

        stage_subtitle_extraction(
            paths=paths,
            execution=resolved_execution,
            resolved_settings=resolved_settings,
        )
        stage_frame_pool(
            paths=paths,
            execution=resolved_execution,
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
            execution=resolved_execution,
            pipeline_settings=pipeline_settings,
        )

        payload = stage_narration_pipeline(
            paths=paths,
            execution=resolved_execution,
            pipeline_settings=pipeline_settings,
            subtitle_context_index_dir=subtitle_context_index_dir,
            job_id=job_id,
            narrator=narrator,
            polisher=polisher,
            synthesizer=synthesizer,
        )
        payload = stage_video_package(
            paths=paths,
            execution=resolved_execution,
            pipeline_settings=pipeline_settings,
            payload=payload,
            video_renderer=video_renderer,
        )
        payload["workflowArtifacts"] = WorkflowArtifacts(
            video_path=paths.source_video,
            srt_path=paths.srt_path,
            frame_pool_manifest=(
                paths.frame_pool_manifest if frame_pool_manifest.is_file() else None
            ),
            subtitle_context_index_dir=subtitle_context_index_dir,
            output_root=str(output_root),
        ).to_payload_dict()
        result = export_workflow_artifacts(
            payload=payload,
            paths=paths,
            output_root=output_root,
        )
        emit_event(log_events.WORKFLOW_DONE, status="ok")
        _write_workflow_manifest(
            path=workflow_json_path,
            status="succeeded",
            job_id=job_id,
            input_video_path=resolved_video_path,
            output_root=output_root,
            user_id=resolved_context.request.user_id,
            log_path=workflow_log_path,
            artifacts=dict(result.get("workflowArtifacts") or {}),
        )
        return result
    except Exception as exc:
        error_fields = classify_error(exc)
        emit_event(
            log_events.WORKFLOW_FAILED,
            level=logging.ERROR,
            status="error",
            fatal=True,
            **error_fields,
        )
        _write_workflow_manifest(
            path=workflow_json_path,
            status="failed",
            job_id=job_id,
            input_video_path=resolved_video_path,
            output_root=output_root,
            user_id=resolved_context.request.user_id,
            log_path=workflow_log_path,
            error=error_fields,
        )
        raise
    finally:
        reset_pipeline_log_context(log_token)
        shutdown_async_logging()
