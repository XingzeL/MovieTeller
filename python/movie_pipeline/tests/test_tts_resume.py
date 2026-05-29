from __future__ import annotations

import json
from pathlib import Path

import pytest

from movie_pipeline.tts_resume import (
    payload_speech_complete,
    speech_completion_summary,
    tts_segment_is_reusable,
)


def test_tts_segment_is_reusable_requires_audio_and_metadata(tmp_path: Path) -> None:
    audio = tmp_path / "seg.mp3"
    meta = tmp_path / "seg.mp3.jsonl"
    assert tts_segment_is_reusable(audio_path=audio, metadata_path=meta) is False

    audio.write_bytes(b"\x00\x01")
    assert tts_segment_is_reusable(audio_path=audio, metadata_path=meta) is False

    meta.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    assert tts_segment_is_reusable(audio_path=audio, metadata_path=meta) is True


def test_speech_completion_summary_counts_missing_speech() -> None:
    payload = {
        "narratedSegments": [
            {"speech": {"audioPath": "/a.mp3"}},
            {"speech": None},
            {},
        ]
    }
    summary = speech_completion_summary(payload)
    assert summary == {"complete": False, "total": 3, "succeeded": 1, "failed": 2}
    assert payload_speech_complete(payload) is False


def test_speech_completion_summary_empty_segments() -> None:
    summary = speech_completion_summary({"narratedSegments": []})
    assert summary["complete"] is True
    assert summary["total"] == 0
