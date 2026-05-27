from __future__ import annotations

from movieteller_logging import events
from movieteller_logging.overall_progress import overall_progress
from movieteller_logging.stage_registry import resolve_macro
from movieteller_logging.progress import progress_from_events


def test_overall_progress_succeeded_is_100_percent() -> None:
    job = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "stage": "workflow"},
            {"event": events.WORKFLOW_DONE, "stage": "workflow"},
        ]
    )
    out = overall_progress(job)
    assert out["status"] == "succeeded"
    assert out["percent"] == 100
    assert out["label"] == "完成"


def test_overall_progress_narration_groups_increase_percent() -> None:
    job = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "stage": "workflow"},
            {"event": events.SUBTITLE_EXTRACTION_DONE, "stage": "subtitle_extraction"},
            {"event": events.FRAME_POOL_DONE, "stage": "frame_pool"},
            {"event": events.SUBTITLE_CONTEXT_DONE, "stage": "subtitle_context"},
            {
                "event": events.STAGE_GROUP_PROGRESS,
                "stage": "narration_group",
                "completed": 2,
                "total": 4,
            },
        ]
    )
    out = overall_progress(job)
    assert out["status"] in {"running", "unknown"}
    assert 40 <= int(out["percent"]) <= 85
    assert out["label"] == "生成旁白"


def test_overall_progress_maps_deprecated_narration_pipeline_alias() -> None:
    job = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "stage": "workflow"},
            {"event": events.FRAME_POOL_DONE, "stage": "frame_pool"},
            {"event": events.STAGE_GROUP_PROGRESS, "stage": "narration_pipeline", "completed": 1, "total": 2},
        ]
    )
    out = overall_progress(job)
    assert resolve_macro(job.current_stage) == "narration"
    assert out["label"] == "生成旁白"


def test_overall_progress_shows_tts_macro_stage_label() -> None:
    job = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "stage": "workflow"},
            {"event": events.STAGE_GROUP_PROGRESS, "stage": "narration_group", "completed": 1, "total": 3},
            {"event": events.SEGMENT_TTS_START, "stage": "tts", "capability": "tts"},
        ]
    )
    out = overall_progress(job)
    assert resolve_macro(job.current_stage) == "tts"
    assert out["label"] == "语音合成"


def test_overall_progress_does_not_regress_from_tts_to_narration_group() -> None:
    job = progress_from_events(
        [
            {"event": events.WORKFLOW_START, "stage": "workflow"},
            {"event": events.SEGMENT_TTS_START, "stage": "tts", "capability": "tts"},
            {"event": events.STAGE_GROUP_PROGRESS, "stage": "narration_group", "completed": 2, "total": 3},
        ]
    )
    out = overall_progress(job)
    assert job.current_stage == "tts"
    assert out["label"] == "语音合成"
