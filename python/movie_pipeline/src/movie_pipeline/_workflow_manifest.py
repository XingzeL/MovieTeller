"""Persist ``workflow.json`` job manifest (decoupled from stage orchestration)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from movieteller_logging import overall_progress, progress_from_jsonl

from movie_pipeline.job import JobRecord, write_job_record


def write_workflow_manifest(
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
    if log_path:
        job_progress = progress_from_jsonl(log_path)
        progress = job_progress.to_dict()
        progress["overall"] = overall_progress(job_progress)
    else:
        progress = {}
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
