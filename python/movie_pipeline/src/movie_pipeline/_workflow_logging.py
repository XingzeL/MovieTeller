"""Workflow-scoped async logging: configure, bind context, flush, shutdown."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from movieteller_config.schema import Settings
from movieteller_logging import (
    bind_pipeline_log_context,
    configure_async_logging,
    emit_event,
    flush_async_logging,
    reset_pipeline_log_context,
    shutdown_async_logging,
)
from movieteller_logging import events as log_events


def configure_workflow_log_file(
    *,
    settings: Settings,
    job_id: str,
    output_root: Path,
    log_to_stderr: bool | None = None,
) -> str | None:
    """Start async JSONL logging; return log file path when enabled."""
    log_opts = settings.pipeline_logging_options()
    log_file = str(output_root / "logs" / "workflow.jsonl")
    stderr = log_opts.stderr if log_to_stderr is None else log_to_stderr
    configure_async_logging(
        enabled=log_opts.enabled,
        level=log_opts.level,
        format=log_opts.format,
        stderr=stderr,
        file=log_file,
    )
    if log_opts.enabled:
        emit_event(
            log_events.WORKFLOW_LOGGING_CONFIGURED,
            job_id=job_id,
            status="ok",
            x_log_path=log_file,
        )
        return log_file
    return None


class WorkflowLogSession:
    """Bind ``job_id`` / workflow extras for one ``run_full_workflow``; reset + shutdown on exit."""

    def __init__(
        self,
        *,
        settings: Settings,
        job_id: str,
        output_root: Path,
        video_path: str,
        log_to_stderr: bool | None = None,
    ) -> None:
        self.settings = settings
        self.job_id = job_id
        self.output_root = output_root
        self.video_path = video_path
        self.log_to_stderr = log_to_stderr
        self._log_file_path: str | None = None
        self._token: Any = None

    @property
    def log_file_path(self) -> str | None:
        return self._log_file_path

    def __enter__(self) -> WorkflowLogSession:
        self._log_file_path = configure_workflow_log_file(
            settings=self.settings,
            job_id=self.job_id,
            output_root=self.output_root,
            log_to_stderr=self.log_to_stderr,
        )
        self._token = bind_pipeline_log_context(
            job_id=self.job_id,
            stage="workflow",
            x_video_path=str(self.video_path),
            x_output_root=str(self.output_root),
        )
        return self

    def flush(self) -> None:
        flush_async_logging()

    def __exit__(self, *args: object) -> None:
        if self._token is not None:
            reset_pipeline_log_context(self._token)
        shutdown_async_logging()
