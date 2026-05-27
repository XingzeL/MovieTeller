"""Single source of truth for workflow macro stages and JSONL ``stage`` aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProgressMode = Literal["groups", "indeterminate"]

# Maps pre-macro / bootstrap context stages to the first macro bucket for percent calc.
BOOTSTRAP_STAGE_ALIASES: dict[str, str] = {
    "workflow": "subtitle_extraction",
}


@dataclass(frozen=True)
class MacroStage:
    """Product-facing macro stage (observation contract + CLI + overall percent)."""

    id: str
    label: str
    weight: float
    log_aliases: frozenset[str] = frozenset()
    children: frozenset[str] = frozenset()
    progress_mode: ProgressMode = "indeterminate"


MACRO_STAGES: tuple[MacroStage, ...] = (
    MacroStage(
        id="subtitle_extraction",
        label="提取字幕",
        weight=0.08,
        log_aliases=frozenset({"subtitle_extraction"}),
    ),
    MacroStage(
        id="frame_pool",
        label="构建帧池",
        weight=0.12,
        log_aliases=frozenset({"frame_pool"}),
    ),
    MacroStage(
        id="subtitle_context",
        label="构建字幕上下文",
        weight=0.08,
        log_aliases=frozenset({"subtitle_context"}),
    ),
    MacroStage(
        id="narration",
        label="生成旁白",
        weight=0.50,
        log_aliases=frozenset(
            {
                "narration",
                "narration_candidates",
                "narration_group",
                "narration_pipeline",  # deprecated CLI / legacy
            }
        ),
        progress_mode="groups",
    ),
    MacroStage(
        id="tts",
        label="语音合成",
        weight=0.15,
        log_aliases=frozenset({"tts"}),
    ),
    MacroStage(
        id="video_package",
        label="封装视频",
        weight=0.04,
        log_aliases=frozenset({"video_package"}),
    ),
    MacroStage(
        id="workflow_export",
        label="导出产物",
        weight=0.03,
        log_aliases=frozenset({"workflow_export"}),
    ),
)

TERMINAL_LABELS: dict[str, str] = {
    "narration": "旁白管线",
}

OVERALL_STATUS_LABELS: dict[str, str] = {
    "queued": "排队中",
    "succeeded": "完成",
    "failed": "失败",
    "running": "处理中",
    "unknown": "处理中",
}

_MACRO_BY_ID: dict[str, MacroStage] = {stage.id: stage for stage in MACRO_STAGES}
_LOG_ALIAS_TO_MACRO: dict[str, str] = {}
for _stage in MACRO_STAGES:
    for _alias in _stage.log_aliases:
        _LOG_ALIAS_TO_MACRO[_alias] = _stage.id
    _LOG_ALIAS_TO_MACRO[_stage.id] = _stage.id
for _bootstrap, _macro in BOOTSTRAP_STAGE_ALIASES.items():
    _LOG_ALIAS_TO_MACRO[_bootstrap] = _macro


def macro_stage_ids() -> tuple[str, ...]:
    """Ordered macro IDs for CLI equal-step display and overall percent."""
    return tuple(stage.id for stage in MACRO_STAGES)


def macro_weights() -> dict[str, float]:
    return {stage.id: stage.weight for stage in MACRO_STAGES}


def macro_label(stage_id: str, *, terminal: bool = False) -> str:
    if terminal and stage_id in TERMINAL_LABELS:
        return TERMINAL_LABELS[stage_id]
    stage = _MACRO_BY_ID.get(stage_id)
    if stage is not None:
        return stage.label
    return stage_id


def stage_label(stage: str | None, *, terminal: bool = False) -> str | None:
    if not stage:
        return None
    key = stage.strip()
    if not key:
        return None
    macro = resolve_macro(key)
    if macro is None:
        return None
    return macro_label(macro, terminal=terminal)


def resolve_macro(stage: str | None) -> str | None:
    """Map a JSONL ``stage`` field (or alias) to a macro stage id."""
    if not stage:
        return None
    key = stage.strip()
    if not key:
        return None
    return _LOG_ALIAS_TO_MACRO.get(key)


def macro_index(macro_id: str | None) -> int:
    if macro_id is None:
        return 0
    try:
        return macro_stage_ids().index(macro_id)
    except ValueError:
        return 0


def progress_mode_for_macro(macro_id: str | None) -> ProgressMode:
    if macro_id is None:
        return "indeterminate"
    stage = _MACRO_BY_ID.get(macro_id)
    if stage is None:
        return "indeterminate"
    return stage.progress_mode


def all_registered_log_stages() -> frozenset[str]:
    """All ``stage`` strings that resolve to a macro (including bootstrap keys)."""
    keys = set(_LOG_ALIAS_TO_MACRO.keys())
    keys.update(BOOTSTRAP_STAGE_ALIASES.keys())
    return frozenset(keys)
