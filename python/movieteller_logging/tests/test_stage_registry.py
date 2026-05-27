from __future__ import annotations

import pytest

from movieteller_logging.stage_registry import (
    BOOTSTRAP_STAGE_ALIASES,
    MACRO_STAGES,
    all_registered_log_stages,
    macro_stage_ids,
    macro_weights,
    resolve_macro,
    stage_label,
)

# Stages observed in emit_event(..., stage=...) across the repo (production).
_KNOWN_EMIT_LOG_STAGES = frozenset(
    {
        "subtitle_extraction",
        "frame_pool",
        "subtitle_context",
        "narration",
        "narration_candidates",
        "narration_group",
        "tts",
        "video_package",
        "workflow_export",
        "workflow",
        "narration_pipeline",
    }
)


def test_macro_weights_sum_to_one() -> None:
    assert sum(macro_weights().values()) == pytest.approx(1.0)


def test_macro_stage_ids_match_registry_order() -> None:
    assert macro_stage_ids() == tuple(stage.id for stage in MACRO_STAGES)


@pytest.mark.parametrize(
    ("log_stage", "expected_macro"),
    [
        ("subtitle_extraction", "subtitle_extraction"),
        ("frame_pool", "frame_pool"),
        ("subtitle_context", "subtitle_context"),
        ("narration", "narration"),
        ("narration_candidates", "narration"),
        ("narration_group", "narration"),
        ("narration_pipeline", "narration"),
        ("tts", "tts"),
        ("video_package", "video_package"),
        ("workflow_export", "workflow_export"),
        ("workflow", "subtitle_extraction"),
    ],
)
def test_resolve_macro_maps_log_stages(log_stage: str, expected_macro: str) -> None:
    assert resolve_macro(log_stage) == expected_macro


def test_all_known_emit_stages_resolve_to_macro() -> None:
    missing = sorted(
        stage for stage in _KNOWN_EMIT_LOG_STAGES if resolve_macro(stage) is None
    )
    assert missing == []


def test_registered_log_stages_cover_known_emit() -> None:
    registered = all_registered_log_stages()
    assert _KNOWN_EMIT_LOG_STAGES <= registered


def test_bootstrap_aliases_point_at_valid_macro() -> None:
    for macro in BOOTSTRAP_STAGE_ALIASES.values():
        assert macro in macro_stage_ids()


def test_stage_label_can_show_tts_macro_stage() -> None:
    assert stage_label("tts") == "语音合成"
    assert stage_label("tts", terminal=True) == "语音合成"
