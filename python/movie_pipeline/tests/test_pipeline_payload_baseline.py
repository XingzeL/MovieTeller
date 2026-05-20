"""Golden-path shape checks for pipeline JSON (refactor safety net)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from movie_pipeline import MoviePipelineOptions, run_pipeline_ctx
from movie_pipeline.runtime_context import RunContext
from movieteller_config.schema import settings_from_dict

_SINGLE_GAP_SRT = """1
00:00:01,250 --> 00:00:02,250
x
"""
_SINGLE_GAP_VIDEO_DUR = 2.3

_EXPECTED_TOP_LEVEL_KEYS_TEXT = frozenset(
    {
        "videoDurationSec",
        "subtitleSpans",
        "rawGaps",
        "narrationCandidates",
        "narratedSegments",
        "speechOutputDir",
        "subtitleContextIndexDir",
        "renderedVideo",
    }
)

_EXPECTED_SEGMENT_KEYS = frozenset(
    {
        "startSec",
        "endSec",
        "durationSec",
        "text",
        "speechText",
        "prevSubtitleText",
        "nextSubtitleText",
        "polish",
        "speech",
        "timingExtractSec",
        "timingApiSec",
        "timingTotalSec",
        "frameCount",
    }
)


def _minimal_settings():
    return settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "model_defaults": {
                "narration": "gpt-4o-mini",
                "polish": "gpt-4.1-mini",
                "tts": "qwen3-tts-flash",
                "embedding": "text-embedding-3-small",
            },
            "ffmpeg_path": "ffmpeg",
            "max_frames_per_segment": 4,
            "narration_frame_max_edge": 768,
            "pool_miss_uniform_max_frames": 2,
            "tts_defaults": {"voice": "en-US-EmmaMultilingualNeural"},
        }
    )


def test_run_pipeline_ctx_payload_top_level_and_segment_keys():
    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    settings = _minimal_settings()
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)
    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(_SINGLE_GAP_SRT, encoding="utf-8")
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            narrator=fake_narrator,
        )
    assert set(payload.keys()) == _EXPECTED_TOP_LEVEL_KEYS_TEXT
    seg0 = payload["narratedSegments"][0]
    assert set(seg0.keys()) == _EXPECTED_SEGMENT_KEYS
    assert seg0["text"] == "narration"
    assert seg0["speechText"] == "narration"
    assert seg0["polish"] is None
    assert seg0["speech"] is None
