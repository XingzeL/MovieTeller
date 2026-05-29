from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def tts_segment_is_reusable(*, audio_path: Path, metadata_path: Path) -> bool:
    if not audio_path.is_file() or audio_path.stat().st_size <= 0:
        return False
    if not metadata_path.is_file() or metadata_path.stat().st_size <= 0:
        return False
    try:
        lines = [
            line.strip()
            for line in metadata_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not lines:
            return False
        json.loads(lines[-1])
    except (OSError, json.JSONDecodeError):
        return False
    return True


def payload_speech_complete(payload: Mapping[str, Any]) -> bool:
    """True when every narrated segment has speech metadata (TTS done or cached)."""
    return speech_completion_summary(payload)["complete"]


def speech_completion_summary(payload: Mapping[str, Any]) -> dict[str, int | bool]:
    segments = payload.get("narratedSegments")
    if not isinstance(segments, list):
        return {"complete": True, "total": 0, "succeeded": 0, "failed": 0}
    total = len(segments)
    succeeded = sum(
        1 for segment in segments if isinstance(segment, dict) and segment.get("speech")
    )
    failed = total - succeeded
    return {
        "complete": failed == 0,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
    }
