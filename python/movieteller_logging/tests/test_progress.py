from __future__ import annotations

import json
from pathlib import Path

from movieteller_logging import events
from movieteller_logging.progress import progress_from_events, progress_from_jsonl


def test_progress_from_events_summarizes_successful_workflow() -> None:
    progress = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "job_id": "job-1", "stage": "workflow"},
            {
                "event": events.SUBTITLE_EXTRACTION_DONE,
                "job_id": "job-1",
                "stage": "subtitle_extraction",
                "status": "skipped",
                "x_srt_path": "/tmp/demo.srt",
            },
            {
                "event": events.STAGE_GROUP_PROGRESS,
                "job_id": "job-1",
                "stage": "narration_group",
                "completed": 2,
                "total": 3,
            },
            {
                "event": events.SEGMENT_DONE,
                "job_id": "job-1",
                "stage": "narration",
                "segment_index": 7,
            },
            {
                "event": events.WORKFLOW_EXPORT_DONE,
                "job_id": "job-1",
                "stage": "workflow_export",
                "x_output_root": "/tmp/out",
            },
            {"event": events.WORKFLOW_DONE, "job_id": "job-1", "stage": "workflow"},
        ]
    )

    assert progress.status == "succeeded"
    assert progress.job_id == "job-1"
    assert progress.current_stage == "workflow"
    assert progress.completed_groups == 2
    assert progress.total_groups == 3
    assert progress.completed_segments == 1
    assert progress.failed_segments == 0
    assert progress.last_event == events.WORKFLOW_DONE
    assert progress.artifacts["srt_path"] == "/tmp/demo.srt"
    assert progress.artifacts["output_root"] == "/tmp/out"


def test_progress_from_events_tracks_failure_and_warning() -> None:
    progress = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "job_id": "job-2", "stage": "workflow"},
            {
                "event": events.STUDY_CARD_EXPORT_FAILED,
                "level": "WARNING",
                "status": "warning",
                "stage": "workflow_export",
                "error_type": "ValueError",
                "error_message": "bad card",
                "error_code": "study_card_export_failed",
                "fatal": False,
                "retryable": False,
            },
            {
                "event": events.SEGMENT_FAILED,
                "status": "error",
                "stage": "narration",
                "segment_index": 3,
                "error_type": "RuntimeError",
                "error_message": "boom",
                "error_code": "provider_500",
                "fatal": True,
                "retryable": True,
            },
            {
                "event": events.WORKFLOW_FAILED,
                "status": "error",
                "stage": "workflow",
                "error_type": "RuntimeError",
                "error_message": "segment 3 failed",
                "error_code": "internal_error",
                "fatal": True,
                "retryable": True,
            },
        ]
    )

    assert progress.status == "failed"
    assert progress.failed_segments == 1
    assert progress.last_error is not None
    assert progress.last_error["event"] == events.WORKFLOW_FAILED
    assert progress.last_error["error_code"] == "internal_error"
    assert progress.fatal_error_count == 2
    assert progress.retryable_error_count == 2
    assert len(progress.warnings) == 1
    assert progress.warnings[0]["event"] == events.STUDY_CARD_EXPORT_FAILED
    assert progress.warnings[0]["fatal"] is False


def test_progress_from_jsonl_reads_file(tmp_path: Path) -> None:
    log_path = tmp_path / "workflow.jsonl"
    rows = [
        {"event": events.WORKFLOW_START, "job_id": "job-file"},
        {"event": events.WORKFLOW_DONE, "job_id": "job-file"},
    ]
    log_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    progress = progress_from_jsonl(log_path)

    assert progress.job_id == "job-file"
    assert progress.status == "succeeded"
