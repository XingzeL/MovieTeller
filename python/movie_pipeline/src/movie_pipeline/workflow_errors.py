from __future__ import annotations

from typing import Any

from movieteller_logging import classify_error


def workflow_error_from_exception(
    exc: BaseException,
    *,
    stage: str | None = None,
    capability: str | None = None,
    segment_index: int | None = None,
    fatal: bool = True,
) -> dict[str, Any]:
    fields = classify_error(exc)
    return {
        **fields,
        "stage": stage,
        "capability": capability,
        "segment_index": segment_index,
        "fatal": fatal,
        "message": fields.get("error_message") or str(exc),
    }
