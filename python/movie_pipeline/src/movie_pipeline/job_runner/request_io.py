from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from movie_pipeline.types import WorkflowRequest

_BOOL_KEYS = (
    "enableSubtitleContext",
    "enablePolish",
    "enableSpeech",
    "enableEmbedVideo",
    "forceRebuildSubtitles",
    "forceRebuildFramePool",
    "forceRebuildSubtitleContext",
)
_FLOAT_KEYS = ("minGapSec", "subtitleGuardSec", "maxCostUsd", "maxLatencySec")
_STR_KEYS = (
    "promptStyle",
    "cefrLevel",
    "ttsVoice",
    "ttsLanguage",
    "userId",
    "userTier",
    "planCode",
    "requestPriority",
    "costMode",
    "sourceLanguage",
    "narrationLanguage",
    "subtitleLanguage",
)


def _optional_bool(data: dict[str, Any], key: str) -> bool | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _optional_float(data: dict[str, Any], key: str) -> float | None:
    if key not in data or data[key] is None or data[key] == "":
        return None
    return float(data[key])


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    if key not in data or data[key] is None:
        return None
    text = str(data[key]).strip()
    return text or None


def workflow_request_from_api_dict(
    data: dict[str, Any],
    *,
    video_path: str,
) -> WorkflowRequest:
    """Map camelCase API / request.json fields to WorkflowRequest."""
    kwargs: dict[str, Any] = {"video_path": video_path}
    for key in _BOOL_KEYS:
        snake = _camel_to_snake(key)
        value = _optional_bool(data, key)
        if value is not None:
            kwargs[snake] = value
    for key in _FLOAT_KEYS:
        snake = _camel_to_snake(key)
        value = _optional_float(data, key)
        if value is not None:
            kwargs[snake] = value
    for key in _STR_KEYS:
        snake = _camel_to_snake(key)
        value = _optional_str(data, key)
        if value is not None:
            kwargs[snake] = value
    if _optional_str(data, "outputRoot"):
        kwargs["output_root"] = _optional_str(data, "outputRoot")
    return WorkflowRequest(**kwargs)


def load_workflow_request_json(path: str | Path, *, video_path: str) -> WorkflowRequest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("request JSON must be an object")
    return workflow_request_from_api_dict(raw, video_path=video_path)


def _camel_to_snake(name: str) -> str:
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out)
