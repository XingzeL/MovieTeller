"""Golden-path shape checks for pipeline JSON (refactor safety net)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from frame_source import FrameSourceOptions
from movie_pipeline import (
    NarrationPipelineConfig,
    parse_pipeline_render_dict,
    parse_pipeline_speech_dict,
    parse_pipeline_text_dict,
    parse_rendered_video_dict,
    parse_workflow_payload_dict,
    run_pipeline_ctx,
)
from movie_pipeline.payload_schema import validate_workflow_artifacts_dict
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
        "studyCard",
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
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=FrameSourceOptions(
            ffmpeg_bin=settings.ffmpeg_path,
            max_frames_per_segment=settings.max_frames_per_segment,
            max_edge_pixels=settings.narration_frame_max_edge,
            pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
        ),
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
    assert seg0["studyCard"] is None
    assert seg0["polish"] is None
    assert seg0["speech"] is None


def test_parse_pipeline_text_dict_rejects_rendered_video_key():
    payload = {
        "narratedSegments": [
            {"startSec": 0.0, "endSec": 1.0, "text": "x"}
        ],
        "renderedVideo": {"outputPath": "bad.mp4"},
    }
    try:
        parse_pipeline_text_dict(payload)
    except ValueError as exc:
        assert "unexpected keys" in str(exc)
        assert "renderedVideo" in str(exc)
    else:
        raise AssertionError("text payload should reject renderedVideo")


def test_parse_pipeline_text_dict_rejects_unknown_segment_key():
    payload = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "durationSec": 1.0,
                "text": "x",
                "speechText": "x",
                "extra": True,
            }
        ],
    }
    try:
        parse_pipeline_text_dict(payload)
    except ValueError as exc:
        assert "narratedSegments[0] contains unexpected keys" in str(exc)
        assert "extra" in str(exc)
    else:
        raise AssertionError("text payload should reject unknown segment keys")


def test_parse_pipeline_speech_dict_requires_speech_audio_path():
    payload = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "durationSec": 1.0,
                "text": "x",
                "speechText": "x",
                "speech": {},
            }
        ]
    }
    try:
        parse_pipeline_speech_dict(payload)
    except ValueError as exc:
        assert "speech missing audioPath" in str(exc)
    else:
        raise AssertionError("speech payload should require audioPath")


def test_parse_pipeline_speech_dict_rejects_rendered_video_key():
    payload = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "durationSec": 1.0,
                "text": "x",
                "speechText": "x",
                "speech": {"audioPath": "x.mp3"},
            }
        ],
        "renderedVideo": {"outputPath": "bad.mp4"},
    }
    try:
        parse_pipeline_speech_dict(payload)
    except ValueError as exc:
        assert "speech payload contains unexpected keys" in str(exc)
        assert "renderedVideo" in str(exc)
    else:
        raise AssertionError("speech payload should reject renderedVideo")


def test_parse_pipeline_render_dict_requires_rendered_video_contract():
    payload = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "durationSec": 1.0,
                "text": "x",
                "speechText": "x",
                "speech": {"audioPath": "x.mp3"},
            }
        ],
        "renderedVideo": {"videoPath": "in.mp4"},
    }
    try:
        parse_pipeline_render_dict(payload)
    except ValueError as exc:
        assert "renderedVideo missing required key 'outputPath'" in str(exc)
    else:
        raise AssertionError("render payload should require renderedVideo.outputPath")


def test_parse_rendered_video_dict_rejects_unknown_keys():
    try:
        parse_rendered_video_dict(
            {"videoPath": "in.mp4", "outputPath": "out.mp4", "extra": True}
        )
    except ValueError as exc:
        assert "renderedVideo contains unexpected keys" in str(exc)
        assert "extra" in str(exc)
    else:
        raise AssertionError("renderedVideo should reject unknown keys")


def test_validate_workflow_artifacts_dict_contract():
    artifacts = validate_workflow_artifacts_dict(
        {
            "videoPath": "demo.mp4",
            "srtPath": "demo.srt",
            "framePoolManifest": None,
            "subtitleContextIndexDir": None,
            "outputRoot": "/tmp/out",
            "textJsonPath": "text.json",
            "speechJsonPath": None,
            "renderJsonPath": None,
            "finalSrtPath": None,
            "studyCardsHtmlPath": None,
            "studyCardsHtmlError": None,
        }
    )

    assert artifacts is not None
    assert artifacts["textJsonPath"] == "text.json"


def test_parse_workflow_payload_dict_accepts_workflow_artifacts_overlay():
    payload = {
        "videoDurationSec": 1.0,
        "subtitleSpans": [],
        "rawGaps": [],
        "narrationCandidates": [],
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "durationSec": 1.0,
                "text": "x",
                "speechText": "x",
                "prevSubtitleText": None,
                "nextSubtitleText": None,
                "studyCard": None,
                "polish": None,
                "speech": None,
                "timingExtractSec": None,
                "timingApiSec": None,
                "timingTotalSec": None,
                "frameCount": None,
            }
        ],
        "speechOutputDir": None,
        "subtitleContextIndexDir": None,
        "subtitleMerge": {
            "sourceSrtPath": "demo.srt",
            "speechVideoJsonPath": "speech.json",
            "outputSrtPath": "final.srt",
            "insertedCueCount": 1,
            "totalCueCount": 2,
        },
        "workflowArtifacts": {
            "videoPath": "demo.mp4",
            "srtPath": "demo.srt",
            "framePoolManifest": None,
            "subtitleContextIndexDir": None,
            "outputRoot": "/tmp/out",
            "studyCardsHtmlPath": None,
            "studyCardsHtmlError": None,
        },
    }

    parsed = parse_workflow_payload_dict(payload)

    assert parsed["workflowArtifacts"]["videoPath"] == "demo.mp4"
    assert parsed["subtitleMerge"]["outputSrtPath"] == "final.srt"


def test_validate_workflow_artifacts_dict_rejects_unknown_keys():
    try:
        validate_workflow_artifacts_dict(
            {
                "videoPath": "demo.mp4",
                "srtPath": "demo.srt",
                "framePoolManifest": None,
                "subtitleContextIndexDir": None,
                "outputRoot": "/tmp/out",
                "bad": True,
            }
        )
    except ValueError as exc:
        assert "workflowArtifacts contains unexpected keys" in str(exc)
        assert "bad" in str(exc)
    else:
        raise AssertionError("workflowArtifacts should reject unknown keys")
