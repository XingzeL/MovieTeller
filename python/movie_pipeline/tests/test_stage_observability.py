from __future__ import annotations

import json
from pathlib import Path

from movieteller_logging import configure_async_logging, flush_async_logging, shutdown_async_logging
from movieteller_logging import events as log_events
from movie_pipeline.stage_observability import StageLogger


def test_stage_logger_emits_standard_lifecycle_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "stage.jsonl"
    configure_async_logging(
        enabled=True,
        level="INFO",
        format="jsonl",
        stderr=False,
        file=str(log_path),
    )
    try:
        stage = StageLogger("demo", input_path="in.mp4")
        stage.start()
        stage.skipped("artifact_reused", output_path="out.json")
        flush_async_logging()
    finally:
        shutdown_async_logging()

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == log_events.WORKFLOW_STAGE_START
    assert rows[0]["stage"] == "demo"
    assert rows[0]["status"] == "start"
    assert rows[0]["input_path"] == "in.mp4"
    assert rows[1]["event"] == log_events.WORKFLOW_STAGE_SKIPPED
    assert rows[1]["skip_reason"] == "artifact_reused"
    assert "duration_ms" in rows[1]
