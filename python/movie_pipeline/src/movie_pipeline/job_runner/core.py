from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from movieteller_config.schema import Settings
from movie_pipeline.full_workflow import resolved_run_context_from_request, run_full_workflow
from movie_pipeline.job import JobPaths, JobRecord, JobStore
from movie_pipeline.job_runner.quota_clip import clip_video_to_processed, should_clip_video
from movie_pipeline.types import PolicyContext, WorkflowRequest


def build_job_request(
    *,
    job_id: str,
    jobs_root: str | Path,
    video_path: str | Path,
    request: WorkflowRequest | None = None,
    user_id: str | None = None,
) -> WorkflowRequest:
    """Bind product job identity to a workflow request."""
    paths = JobPaths.resolve(jobs_root=jobs_root, job_id=job_id)
    base = request or WorkflowRequest(video_path=str(video_path))
    return replace(
        base,
        video_path=str(video_path),
        output_root=paths.root,
        workspace_id=job_id,
        user_id=user_id if user_id is not None else base.user_id,
    )


def _maybe_clip_input_video(
    *,
    job_id: str,
    jobs_root: str | Path,
    video_path: str | Path,
    request: WorkflowRequest,
    settings: Settings,
) -> tuple[str, WorkflowRequest]:
    if not should_clip_video(
        start_point=request.start_point,
        end_point=request.end_point,
        source_path=video_path,
    ):
        return str(video_path), request

    paths = JobPaths.resolve(jobs_root=jobs_root, job_id=job_id)
    processed_path = Path(paths.input_dir) / "processed.mp4"
    ffmpeg_bin = getattr(settings, "ffmpeg_path", None) or "ffmpeg"
    clip_video_to_processed(
        source_path=video_path,
        output_path=processed_path,
        start_point=request.start_point,
        end_point=request.end_point,
        ffmpeg_bin=str(ffmpeg_bin),
    )
    clipped_request = replace(
        request,
        video_path=str(processed_path),
        start_point=None,
        end_point=None,
    )
    return str(processed_path), clipped_request


def run_workflow_job(
    *,
    job_id: str,
    jobs_root: str | Path,
    video_path: str | Path,
    settings: Settings,
    request: WorkflowRequest | None = None,
    policy: PolicyContext | None = None,
    user_id: str | None = None,
    narrator: Any = None,
    polisher: Any = None,
    synthesizer: Any = None,
    video_renderer: Any = None,
) -> JobRecord:
    """Run one product job and return the persisted workflow manifest."""
    store = JobStore.resolve(jobs_root=jobs_root, job_id=job_id)
    store.ensure_dirs()
    workflow_request = build_job_request(
        job_id=job_id,
        jobs_root=jobs_root,
        video_path=video_path,
        request=request,
        user_id=user_id,
    )
    effective_video_path, workflow_request = _maybe_clip_input_video(
        job_id=job_id,
        jobs_root=jobs_root,
        video_path=video_path,
        request=workflow_request,
        settings=settings,
    )
    store.write_initial(
        status="running",
        input_video_path=effective_video_path,
        user_id=workflow_request.user_id,
        current_stage="workflow",
    )
    resolved_context = resolved_run_context_from_request(
        request=workflow_request,
        settings=settings,
        policy=policy,
    )
    run_full_workflow(
        resolved_context=resolved_context,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
        video_renderer=video_renderer,
    )
    return store.read()
