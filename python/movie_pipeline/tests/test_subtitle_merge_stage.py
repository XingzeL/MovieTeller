"""Tests for formal subtitle merge API."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from movie_pipeline.subtitle_merge_stage import merge_subtitles_for_narration


def test_merge_subtitles_for_narration_writes_output(tmp_path: Path):
    speech_json = tmp_path / "speech.json"
    speech_json.write_text(
        json.dumps(
            {
                "narratedSegments": [
                    {
                        "startSec": 1.0,
                        "endSec": 2.0,
                        "text": "hello",
                        "speechText": "hello",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_srt = tmp_path / "in.srt"
    source_srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\norig\n",
        encoding="utf-8",
    )
    out_srt = tmp_path / "out.srt"
    result = merge_subtitles_for_narration(
        speech_video_json_path=str(speech_json),
        source_srt_path=str(source_srt),
        output_srt_path=str(out_srt),
    )
    assert out_srt.is_file()
    assert result.output_srt_path == str(out_srt)
    assert result.inserted_cue_count >= 1
