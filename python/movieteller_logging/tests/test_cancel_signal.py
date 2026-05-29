from __future__ import annotations

from pathlib import Path

import pytest

from movieteller_logging.cancel_signal import (
    WorkflowCanceledError,
    ensure_not_canceled_from_log_context,
    is_job_canceled_in_log_context,
    job_output_root_from_log_context,
)
from movieteller_logging.context import (
    bind_pipeline_log_context,
    current_pipeline_extra,
    merge_pipeline_context,
    reset_pipeline_log_context,
)


def test_cancel_signal_reads_flag_from_x_output_root(tmp_path: Path) -> None:
    job_root = tmp_path / "job-1"
    job_root.mkdir()
    token = bind_pipeline_log_context(x_output_root=str(job_root))
    try:
        assert is_job_canceled_in_log_context() is False
        (job_root / "cancel.flag").write_text("2026-01-01T00:00:00Z\n", encoding="utf-8")
        assert is_job_canceled_in_log_context() is True
        with pytest.raises(WorkflowCanceledError):
            ensure_not_canceled_from_log_context()
    finally:
        reset_pipeline_log_context(token)


def test_cancel_signal_no_context_is_noop(tmp_path: Path) -> None:
    job_root = tmp_path / "job-orphan"
    job_root.mkdir()
    (job_root / "cancel.flag").write_text("x\n", encoding="utf-8")
    assert job_output_root_from_log_context() is None
    assert is_job_canceled_in_log_context() is False
    ensure_not_canceled_from_log_context()


def test_cancel_signal_empty_x_output_root_is_noop() -> None:
    token = bind_pipeline_log_context(x_output_root="  ")
    try:
        assert job_output_root_from_log_context() is None
        ensure_not_canceled_from_log_context()
    finally:
        reset_pipeline_log_context(token)


def test_merge_pipeline_context_preserves_x_output_root(tmp_path: Path) -> None:
    job_root = tmp_path / "job-merge"
    job_root.mkdir()
    outer = bind_pipeline_log_context(
        job_id="job-1",
        stage="workflow",
        x_output_root=str(job_root),
    )
    try:
        inner = merge_pipeline_context(stage="narration_candidates")
        try:
            assert current_pipeline_extra().get("x_output_root") == str(job_root)
            assert current_pipeline_extra().get("job_id") == "job-1"
            assert current_pipeline_extra().get("stage") == "narration_candidates"
            (job_root / "cancel.flag").write_text("x\n", encoding="utf-8")
            with pytest.raises(WorkflowCanceledError):
                ensure_not_canceled_from_log_context()
        finally:
            reset_pipeline_log_context(inner)
        assert current_pipeline_extra().get("x_output_root") == str(job_root)
    finally:
        reset_pipeline_log_context(outer)
