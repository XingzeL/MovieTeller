from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from movieteller_logging import events
from movieteller_logging.reader import read_jsonl_events
from movieteller_logging.stage_registry import macro_index, resolve_macro


@dataclass(frozen=True)
class JobProgress:
    job_id: str | None = None
    status: str = "unknown"
    current_stage: str | None = None
    completed_groups: int = 0
    total_groups: int | None = None
    completed_segments: int = 0
    failed_segments: int = 0
    last_event: str | None = None
    last_error: dict[str, Any] | None = None
    warnings: tuple[dict[str, Any], ...] = ()
    fatal_error_count: int = 0
    retryable_error_count: int = 0
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def progress_from_jsonl(path: str | Path) -> JobProgress:
    return progress_from_events(read_jsonl_events(path))


def progress_from_events(raw_events: Iterable[Mapping[str, Any]]) -> JobProgress:
    status = "unknown"
    job_id: str | None = None
    current_stage: str | None = None
    completed_groups = 0
    total_groups: int | None = None
    completed_segments: set[int] = set()
    failed_segments: set[int] = set()
    last_event: str | None = None
    last_error: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = []
    fatal_error_count = 0
    retryable_error_count = 0
    artifacts: dict[str, Any] = {}

    for row in raw_events:
        event = _str_or_none(row.get("event"))
        if event is None:
            continue
        last_event = event
        job_id = _str_or_none(row.get("job_id")) or job_id
        stage = _str_or_none(row.get("stage"))
        if stage and (
            event in {events.WORKFLOW_DONE, events.WORKFLOW_FAILED}
            or _should_update_current_stage(current_stage, stage)
        ):
            current_stage = stage

        level = _str_or_none(row.get("level"))
        row_status = _str_or_none(row.get("status"))
        if row_status == "warning" or level == "WARNING":
            warnings.append(_compact_issue(row))
        if row_status == "error" or event.endswith(".failed"):
            issue = _compact_issue(row)
            last_error = issue
            if _bool_value(row.get("fatal")):
                fatal_error_count += 1
            if _bool_value(row.get("retryable")):
                retryable_error_count += 1

        if event == events.WORKFLOW_START:
            status = "running"
        elif event == events.WORKFLOW_DONE:
            status = "succeeded"
        elif event == events.WORKFLOW_FAILED:
            status = "failed"

        if event == events.STAGE_GROUP_PROGRESS:
            completed_groups = max(completed_groups, _int_or_zero(row.get("completed")))
            total_groups = _int_or_none(row.get("total")) or total_groups
        elif event == events.STAGE_GROUP_DONE:
            group_index = _int_or_none(row.get("group_index"))
            if group_index is not None:
                completed_groups = max(completed_groups, group_index)
            total_groups = _int_or_none(row.get("total")) or total_groups

        segment_index = _int_or_none(row.get("segment_index"))
        if event == events.SEGMENT_DONE and segment_index is not None:
            completed_segments.add(segment_index)
        elif event == events.SEGMENT_FAILED and segment_index is not None:
            failed_segments.add(segment_index)

        _collect_artifact_fields(row, artifacts)

    if status == "unknown" and last_event is not None:
        status = "running"
    if fatal_error_count > 0 and status != "succeeded":
        status = "failed"

    return JobProgress(
        job_id=job_id,
        status=status,
        current_stage=current_stage,
        completed_groups=completed_groups,
        total_groups=total_groups,
        completed_segments=len(completed_segments),
        failed_segments=len(failed_segments),
        last_event=last_event,
        last_error=last_error,
        warnings=tuple(warnings),
        fatal_error_count=fatal_error_count,
        retryable_error_count=retryable_error_count,
        artifacts=artifacts,
    )


def _compact_issue(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "event",
        "stage",
        "segment_index",
        "capability",
        "error_type",
        "error_message",
        "error_code",
        "retryable",
        "fatal",
    ):
        value = row.get(key)
        if value is not None:
            out[key] = value
    return out


def _should_update_current_stage(current_stage: str | None, next_stage: str) -> bool:
    current_macro = resolve_macro(current_stage)
    next_macro = resolve_macro(next_stage)
    if current_macro is None or next_macro is None:
        return True
    return macro_index(next_macro) >= macro_index(current_macro)


def _collect_artifact_fields(row: Mapping[str, Any], artifacts: dict[str, Any]) -> None:
    for key, value in row.items():
        if value is None:
            continue
        if key in {"x_srt_path", "x_manifest_path", "x_index_dir", "x_video_output_path", "x_output_root"}:
            artifacts[key[2:]] = value


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    return _int_or_none(value) or 0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
