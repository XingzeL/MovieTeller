"""Cooperative cancel checks using pipeline log context (``x_output_root``)."""

from __future__ import annotations

from pathlib import Path

from movieteller_logging.context import current_pipeline_extra


class WorkflowCanceledError(RuntimeError):
    """Raised when ``cancel.flag`` exists under the job output root in log context."""


def job_output_root_from_log_context() -> Path | None:
    extra = current_pipeline_extra()
    raw = extra.get("x_output_root")
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return Path(text).resolve()


def is_job_canceled_in_log_context() -> bool:
    root = job_output_root_from_log_context()
    if root is None:
        return False
    return (root / "cancel.flag").is_file()


def ensure_not_canceled_from_log_context() -> None:
    root = job_output_root_from_log_context()
    if root is not None and (root / "cancel.flag").is_file():
        raise WorkflowCanceledError(f"job canceled: {root}")
