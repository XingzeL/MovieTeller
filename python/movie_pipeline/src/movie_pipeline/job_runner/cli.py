from __future__ import annotations

import argparse
import sys
from pathlib import Path

from movieteller_config import load_settings
from movieteller_logging import classify_error

from movie_pipeline.cancel_check import JobCanceledError
from movie_pipeline.job import JobRecord, JobStore, utc_now_iso
from movie_pipeline.job_runner.core import run_workflow_job
from movie_pipeline.job_runner.request_io import load_workflow_request_json
from movieteller_logging.cancel_signal import WorkflowCanceledError


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Run one MovieTeller product workflow job.")
    ap.add_argument("--job-id", required=True, help="Job identifier")
    ap.add_argument("--jobs-root", required=True, help="Root directory for job artifacts")
    ap.add_argument("--video", required=True, help="Absolute path to input video")
    ap.add_argument(
        "--request-json",
        default=None,
        help="Optional JSON file with camelCase WorkflowRequest options",
    )
    ap.add_argument("--user-id", default=None, help="Optional user id for the job record")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        print(f"video not found: {video_path}", file=sys.stderr)
        return 2

    jobs_root = Path(args.jobs_root).resolve()
    job_id = str(args.job_id).strip()
    store = JobStore.resolve(jobs_root=jobs_root, job_id=job_id)

    request = None
    if args.request_json:
        request = load_workflow_request_json(args.request_json, video_path=str(video_path))

    try:
        settings = load_settings(require_narration=True)
    except Exception as exc:
        _write_failed(store, video_path=video_path, user_id=args.user_id, exc=exc)
        print(str(exc), file=sys.stderr)
        return 1

    try:
        run_workflow_job(
            job_id=job_id,
            jobs_root=jobs_root,
            video_path=video_path,
            settings=settings,
            request=request,
            user_id=args.user_id,
        )
    except (JobCanceledError, WorkflowCanceledError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        _write_failed(store, video_path=video_path, user_id=args.user_id, exc=exc)
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _write_failed(
    store: JobStore,
    *,
    video_path: Path,
    user_id: str | None,
    exc: BaseException,
) -> None:
    store.ensure_dirs()
    error_fields = classify_error(exc)
    now = utc_now_iso()
    try:
        existing = store.read()
        if existing.status in ("canceled", "succeeded"):
            return
        record = JobRecord(
            job_id=existing.job_id,
            status="failed",
            input_video_path=str(video_path),
            output_root=existing.output_root,
            user_id=user_id or existing.user_id,
            current_stage=existing.current_stage,
            progress=existing.progress,
            error=error_fields,
            artifacts=existing.artifacts,
            created_at=existing.created_at,
            updated_at=now,
        )
    except Exception:
        record = JobRecord(
            job_id=store.paths.job_id,
            status="failed",
            input_video_path=str(video_path),
            output_root=store.paths.root,
            user_id=user_id,
            current_stage="workflow",
            error=error_fields,
            created_at=now,
            updated_at=now,
        )
    store.write(record)
