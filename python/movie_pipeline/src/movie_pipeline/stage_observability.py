from __future__ import annotations

import logging
import time
from typing import Any

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events


class StageLogger:
    """Emit standardized workflow.stage lifecycle events for one fixed stage."""

    def __init__(self, stage: str, **fields: Any) -> None:
        self.stage = str(stage)
        self.fields = {k: v for k, v in fields.items() if v is not None}
        self.started_at = time.perf_counter()
        self._terminal_emitted = False

    def start(self, **fields: Any) -> None:
        emit_event(
            log_events.WORKFLOW_STAGE_START,
            stage=self.stage,
            status="start",
            **self._merge(fields),
        )

    def done(self, **fields: Any) -> None:
        self._terminal_emitted = True
        emit_event(
            log_events.WORKFLOW_STAGE_DONE,
            stage=self.stage,
            status="ok",
            duration_ms=self.duration_ms,
            **self._merge(fields),
        )

    def skipped(self, skip_reason: str, **fields: Any) -> None:
        self._terminal_emitted = True
        emit_event(
            log_events.WORKFLOW_STAGE_SKIPPED,
            stage=self.stage,
            status="skipped",
            skip_reason=str(skip_reason),
            duration_ms=self.duration_ms,
            **self._merge(fields),
        )

    def failed(
        self,
        exc: BaseException,
        *,
        fatal: bool = True,
        level: int = logging.ERROR,
        **fields: Any,
    ) -> None:
        self._terminal_emitted = True
        emit_event(
            log_events.WORKFLOW_STAGE_FAILED,
            level=level,
            stage=self.stage,
            status="error",
            duration_ms=self.duration_ms,
            fatal=fatal,
            **self._merge(fields),
            **classify_error(exc),
        )

    @property
    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    def _merge(self, fields: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.fields)
        merged.update({k: v for k, v in fields.items() if v is not None})
        return merged


def skip_reason_from_status(status: str, *, disabled: bool = False) -> str:
    if disabled:
        return "disabled_by_request"
    if status == "skipped":
        return "artifact_reused"
    return "not_requested"
