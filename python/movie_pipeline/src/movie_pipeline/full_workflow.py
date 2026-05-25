"""End-to-end workflow entry: thin orchestration over stages, logging, and manifest.

Resolution helpers live in :mod:`movie_pipeline._workflow_resolve`.
Logging session in :mod:`movie_pipeline._workflow_logging`.
``workflow.json`` writes in :mod:`movie_pipeline._workflow_manifest`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events

from movie_pipeline._workflow_logging import WorkflowLogSession
from movie_pipeline._workflow_manifest import write_workflow_manifest
from movie_pipeline._workflow_resolve import (
    default_policy_context_for_request,
    default_workflow_job_id,
    pipeline_settings_with_resolved_frame_pool,
    resolve_workflow_config,
    resolved_run_context_from_request,
)
from movie_pipeline.job import WorkflowArtifacts
from movie_pipeline.types import ArtifactPaths, ResolvedRunContext
from movie_pipeline.workflow_artifacts import write_stage_artifact_manifest
from movie_pipeline.workflow_exports import export_workflow_artifacts
from movie_pipeline.workflow_stages import (
    stage_frame_pool,
    stage_narration_pipeline,
    stage_subtitle_context,
    stage_subtitle_extraction,
    stage_video_package,
)

__all__ = [
    "default_policy_context_for_request",
    "resolve_workflow_config",
    "resolved_run_context_from_request",
    "run_full_workflow",
]
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
    job_id = default_workflow_job_id(resolved_context, output_root)
    workflow_json_path = output_root / "workflow.json"

    with WorkflowLogSession(
        settings=resolved_settings,
        job_id=job_id,
        output_root=output_root,
        video_path=str(resolved_video_path),
    ) as log_session:
        workflow_log_path = log_session.log_file_path
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
            pipeline_settings = pipeline_settings_with_resolved_frame_pool(
                resolved_settings,
                frame_pool_manifest_path=paths.frame_pool_manifest,
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
            artifact_manifest_path = write_stage_artifact_manifest(paths=paths)
            payload["workflowArtifacts"] = WorkflowArtifacts(
                video_path=paths.source_video,
                srt_path=paths.srt_path,
                frame_pool_manifest=(
                    paths.frame_pool_manifest if frame_pool_manifest.is_file() else None
                ),
                subtitle_context_index_dir=subtitle_context_index_dir,
                output_root=str(output_root),
                artifact_manifest_path=artifact_manifest_path,
            ).to_payload_dict()
            result = export_workflow_artifacts(
                payload=payload,
                paths=paths,
                output_root=output_root,
            )
            emit_event(log_events.WORKFLOW_DONE, status="ok")
            log_session.flush()
            write_workflow_manifest(
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
            log_session.flush()
            write_workflow_manifest(
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
