from __future__ import annotations

import json
import logging
from pathlib import Path

from movieteller_logging import (
    bind_pipeline_log_context,
    configure_async_logging,
    emit_event,
    reset_pipeline_log_context,
    shutdown_async_logging,
)


def test_emit_event_writes_jsonl_record(tmp_path: Path) -> None:
    log_path = tmp_path / "t.jsonl"
    configure_async_logging(
        enabled=True,
        level="INFO",
        format="jsonl",
        stderr=False,
        file=str(log_path),
    )
    try:
        token = bind_pipeline_log_context(job_id="job-1", stage="test")
        try:
            emit_event(
                "unit.test",
                capability="narration",
                provider="p",
                model="m",
                status="ok",
            )
        finally:
            reset_pipeline_log_context(token)
        shutdown_async_logging()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["event"] == "unit.test"
        assert row["job_id"] == "job-1"
        assert row["stage"] == "test"
        assert row["capability"] == "narration"
        assert row["provider"] == "p"
        assert row["model"] == "m"
        assert row["status"] == "ok"
        assert row["level"] == "INFO"
    finally:
        shutdown_async_logging()


def test_emit_event_noop_when_disabled() -> None:
    configure_async_logging(enabled=False)
    emit_event("should.not.crash", level=logging.WARNING)
