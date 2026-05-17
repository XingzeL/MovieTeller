from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline_transcript.speech_video_script import (
    PipelineSpeechVideoScriptOptions,
    build_readable_script,
    load_pipeline_speech_video_json,
)


def test_build_readable_script_minimal(tmp_path: Path) -> None:
    payload = {
        "videoDurationSec": 120.0,
        "narratedSegments": [
            {
                "startSec": 1.0,
                "endSec": 5.0,
                "durationSec": 4.0,
                "text": "Long raw narration.",
                "speechText": "Short line.",
                "prevSubtitleText": "Hello",
                "nextSubtitleText": "World",
            }
        ],
    }
    out = build_readable_script(payload, source_path=tmp_path / "demo.pipeline.json")
    assert "片长（秒）: 120.000" in out
    assert "第 1 段" in out
    assert "0:01.000 – 0:05.000" in out
    assert "前一条：Hello" in out
    assert "后一条：World" in out
    assert "Short line." in out
    assert "Long raw narration." in out


def test_build_readable_script_hides_raw_when_disabled() -> None:
    payload = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "text": "RAW",
                "speechText": "SPOKEN",
                "prevSubtitleText": "",
                "nextSubtitleText": None,
            }
        ],
    }
    out = build_readable_script(
        payload,
        options=PipelineSpeechVideoScriptOptions(include_raw_narration_if_different=False),
    )
    assert "SPOKEN" in out
    assert "RAW" not in out


def test_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(
        json.dumps({"narratedSegments": [{"startSec": 0, "endSec": 1, "text": "a"}]}),
        encoding="utf-8",
    )
    data = load_pipeline_speech_video_json(p)
    assert data["narratedSegments"][0]["text"] == "a"


def test_empty_segments_errors() -> None:
    with pytest.raises(ValueError, match="empty"):
        build_readable_script({"narratedSegments": []})
