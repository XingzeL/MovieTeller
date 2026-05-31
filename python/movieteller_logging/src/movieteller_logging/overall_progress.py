"""Map :class:`JobProgress` to a single product-facing percent + label."""

from __future__ import annotations

from movieteller_logging.progress import JobProgress
from movieteller_logging.stage_registry import (
    OVERALL_STATUS_LABELS,
    macro_index,
    macro_stage_ids,
    macro_weights,
    progress_mode_for_macro,
    resolve_macro,
    user_facing_macro_label,
    user_facing_stage_label,
)


def overall_progress(job: JobProgress) -> dict[str, object]:
    """Return ``{status, percent, label, currentStage}`` for frontend polling."""
    status = job.status
    if status == "succeeded":
        return {
            "status": status,
            "percent": 100,
            "label": OVERALL_STATUS_LABELS["succeeded"],
            "currentStage": job.current_stage,
        }
    if status == "failed":
        percent = _percent_in_flight(job)
        return {
            "status": status,
            "percent": percent,
            "label": OVERALL_STATUS_LABELS["failed"],
            "currentStage": job.current_stage,
            "lastError": job.last_error,
        }

    macro = resolve_macro(job.current_stage)
    percent = _percent_in_flight(job)
    label = user_facing_stage_label(job.current_stage) or (
        user_facing_macro_label(macro) if macro else OVERALL_STATUS_LABELS["running"]
    )
    return {
        "status": status if status != "unknown" else "running",
        "percent": percent,
        "label": label,
        "currentStage": job.current_stage,
    }


def _percent_in_flight(job: JobProgress) -> int:
    macro = resolve_macro(job.current_stage)
    idx = macro_index(macro)
    ordered = macro_stage_ids()
    weights = macro_weights()
    completed_weight = sum(weights[s] for s in ordered[:idx])
    current_key = macro or ordered[min(idx, len(ordered) - 1)]
    current_weight = weights.get(current_key, 0.0)
    mode = progress_mode_for_macro(macro)
    if mode == "groups" and job.total_groups and job.total_groups > 0:
        frac = min(1.0, job.completed_groups / job.total_groups)
    elif current_key in weights:
        frac = 0.35
    else:
        frac = 0.0
    raw = (completed_weight + current_weight * frac) * 100.0
    if job.status == "succeeded":
        return 100
    return max(0, min(99, int(round(raw))))
