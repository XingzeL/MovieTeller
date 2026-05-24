from dataclasses import replace
from pathlib import Path
import json
from threading import Lock
import time

import pytest

from frame_source import FrameSourceOptions
from movieteller_config.schema import settings_from_dict

from movie_pipeline import (
    NarrationPipelineConfig,
    PolicyContext,
    ResolvedExecutionConfig,
    WorkflowRequest,
    render_video_from_narration_payload,
    resolve_workflow_config,
    resolved_run_context_from_request,
    run_full_workflow,
    narrate_analysis_candidates,
    run_pipeline_ctx,
    read_job_record,
)
from movie_pipeline.payload_schema import validate_workflow_artifacts_dict
from movie_pipeline.runtime_context import RunContext
from subtitle_analysis import analyze_srt_text

# One subtitle cue with a single qualifying narration gap before it.
_SINGLE_GAP_SRT = """1
00:00:01,250 --> 00:00:02,250
x
"""
_SINGLE_GAP_VIDEO_DUR = 2.3


def settings_to_frame_source_options(settings):
    return FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )


def make_settings(**overrides):
    base = {
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
    base.update(overrides)
    return settings_from_dict(base)


def test_narrate_analysis_candidates_uses_selected_gaps():
    raw = """1
00:00:00,000 --> 00:00:01,000
a

2
00:00:04,000 --> 00:00:05,000
b
"""
    analysis = analyze_srt_text(
        raw,
        video_duration_sec=8.0,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
    )
    settings = make_settings()
    frame_source_options = settings_to_frame_source_options(settings)
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=8.0,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(prompt_style="documentary"),
        frame_source_options=frame_source_options,
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    calls = []

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        calls.append((video_path, start_sec, end_sec, kwargs["options"].prompt_style))
        timings = kwargs["timings_out"]
        timings["extract_sec"] = 0.1
        timings["api_sec"] = 0.2
        timings["total_sec"] = 0.3
        timings["frame_count"] = 4
        return (f"text-{start_sec:.2f}-{end_sec:.2f}", end_sec - start_sec)

    segments = narrate_analysis_candidates(
        analysis,
        ctx=ctx,
        video_path="demo.mp4",
        frame_source_options=frame_source_options,
        narrator=fake_narrator,
    )
    assert len(segments) == 2
    assert segments[0].narration_text.startswith("text-")
    assert segments[0].frame_count == 4
    assert calls[0][0] == "demo.mp4"


def test_narrate_analysis_candidates_passes_subtitle_context_input():
    raw = """1
00:00:00,000 --> 00:00:01,000
a

2
00:00:04,000 --> 00:00:05,000
b
"""
    analysis = analyze_srt_text(
        raw,
        video_duration_sec=5.2,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
    )
    settings = make_settings()
    frame_source_options = settings_to_frame_source_options(settings)
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=5.2,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=frame_source_options,
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)
    calls = []

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        calls.append(kwargs["narration_context"])
        return ("narration", end_sec - start_sec)

    segments = narrate_analysis_candidates(
        analysis,
        ctx=ctx,
        video_path="demo.mp4",
        subtitle_context_index_dir="demo.subtitle_context",
        frame_source_options=frame_source_options,
        narrator=fake_narrator,
    )
    assert len(segments) == 1
    assert calls[0].prev_subtitle_text == "a"
    assert calls[0].next_subtitle_text == "b"
    assert calls[0].retrieved_context_texts == ()


def test_narrate_analysis_candidates_runs_contiguous_groups_in_parallel_and_preserves_output_order():
    raw = """1
00:00:00,000 --> 00:00:01,000
a

2
00:00:04,000 --> 00:00:05,000
b

3
00:00:08,000 --> 00:00:09,000
c

4
00:00:12,000 --> 00:00:13,000
d
"""
    analysis = analyze_srt_text(
        raw,
        video_duration_sec=16.0,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
    )
    settings = make_settings(
        workflow_parallelism={
            "segment_group_size": 2,
            "segment_group_concurrency": 2,
        },
        capability_concurrency={
            "narration": 2,
            "polish": 1,
            "study_enrichment": 1,
            "tts": 1,
            "subtitle_context": 1,
        },
    )
    frame_source_options = settings_to_frame_source_options(settings)
    ctx = RunContext(
        settings=settings,
        pipeline=NarrationPipelineConfig(
            video_duration_sec=16.0,
            min_gap_sec=1.0,
            subtitle_guard_sec=0.25,
            narration_options=settings.narration_options(),
            frame_source_options=frame_source_options,
        ),
    )
    active = 0
    peak = 0
    lock = Lock()
    call_order: list[float] = []

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            call_order.append(start_sec)
        if start_sec < 6:
            time.sleep(0.04)
        else:
            time.sleep(0.01)
        with lock:
            active -= 1
        return (f"segment-{start_sec:.0f}", end_sec - start_sec)

    segments = narrate_analysis_candidates(
        analysis,
        ctx=ctx,
        video_path="demo.mp4",
        frame_source_options=frame_source_options,
        narrator=fake_narrator,
    )

    assert [segment.narration_text for segment in segments] == [
        "segment-1",
        "segment-5",
        "segment-9",
        "segment-13",
    ]
    assert peak == 2
    first_group = [segment.start_sec for segment in segments[:2]]
    second_group = [segment.start_sec for segment in segments[2:]]
    assert call_order.index(first_group[0]) < call_order.index(first_group[1])
    assert call_order.index(second_group[0]) < call_order.index(second_group[1])


def test_run_pipeline_ctx_returns_timed_json_payload():
    raw = _SINGLE_GAP_SRT

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=settings_to_frame_source_options(settings),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            narrator=fake_narrator,
        )
    assert "narratedSegments" in payload
    assert len(payload["narratedSegments"]) == 1
    assert payload["narratedSegments"][0]["text"] == "narration"
    assert payload["narratedSegments"][0]["speechText"] == "narration"


def test_resolve_workflow_config_applies_request_and_policy_defaults():
    settings = make_settings(
        gateway={"default_provider": "newapi", "tts_provider": "dashscope"},
        api_keys={"newapi": "sk-newapi", "dashscope": "sk-dashscope"},
        api_providers={
            "newapi": "http://127.0.0.1:3000/v1",
            "dashscope": "https://dashscope.aliyuncs.com/api/v1",
        },
        model_defaults={
            "narration": "qwen3-vl-flash",
            "polish": "qwen3-14b",
            "tts": "qwen3-tts-flash",
            "embedding": "text-embedding-v4",
        },
    )
    request = WorkflowRequest(
        video_path="demo.mp4",
        output_root="/tmp/out",
        prompt_style="documentary",
        cefr_level="B2",
        user_tier="free",
        enable_speech=True,
        tts_voice="Cherry",
    )
    policy = PolicyContext(
        resolved_level="free",
        allow_subtitle_context=False,
        allow_polish=False,
        allow_speech=True,
        allow_embed_video=False,
        default_enable_subtitle_context=False,
        default_enable_polish=False,
        default_enable_speech=False,
        default_enable_embed_video=False,
        default_provider_override="newapi",
        tts_provider_override="dashscope",
        capability_model_overrides={"tts": "qwen3-tts-flash"},
    )

    resolved = resolve_workflow_config(
        request=request,
        settings=settings,
        policy=policy,
    )

    assert resolved.request is request
    assert resolved.policy is policy
    assert resolved.settings.default_provider() == "newapi"
    assert resolved.settings.provider_for_capability("tts") == "dashscope"
    assert resolved.settings.default_model_for_capability("tts") == "qwen3-tts-flash"
    assert resolved.execution.enable_speech is True
    assert resolved.execution.enable_polish is False
    assert resolved.execution.build_subtitle_context is False
    assert resolved.execution.output_root == "/tmp/out"
    assert resolved.execution.pipeline.speech_options is not None
    assert resolved.execution.pipeline.speech_options.voice == "Cherry"
    assert resolved.execution.pipeline.narration_options is not None
    assert resolved.execution.pipeline.narration_options.prompt_style == "documentary"
    assert resolved.execution.pipeline.polish_options is None


def test_resolved_run_context_from_request_wraps_resolved_config():
    settings = make_settings()
    request = WorkflowRequest(video_path="demo.mp4", user_tier="pro")

    resolved = resolved_run_context_from_request(
        request=request,
        settings=settings,
    )

    assert resolved.video_path == "demo.mp4"
    assert resolved.request is request
    assert resolved.execution.enable_polish is True
    assert resolved.execution.build_subtitle_context is True


def test_run_full_workflow_accepts_resolved_context(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    srt = tmp_path / "demo.extracted.srt"
    srt.write_text(_SINGLE_GAP_SRT, encoding="utf-8")
    pool_dir = tmp_path / "demo.frame_pool"
    pool_dir.mkdir()
    (pool_dir / "manifest.jsonl").write_text("", encoding="utf-8")
    ctx_dir = tmp_path / "demo.subtitle_context"
    ctx_dir.mkdir()
    (ctx_dir / "chunks.jsonl").write_text("", encoding="utf-8")

    import numpy as np

    np.save(ctx_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))

    settings = make_settings()
    request = WorkflowRequest(video_path=str(video), output_root=str(tmp_path))
    resolved_context = resolved_run_context_from_request(
        request=request,
        settings=settings,
    )
    assert resolved_context.execution.pipeline is not None
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=replace(
                resolved_context.execution,
                pipeline=replace(
                    resolved_context.execution.pipeline,
                    video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                ),
            ),
        )
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    import movie_pipeline.workflow_stages as ws

    original_run_pipeline_ctx = ws.run_pipeline_ctx
    captured = {}

    def fake_run_pipeline_ctx(*, srt_path, video_path, ctx, narrator=None, **kwargs):
        captured["video_path"] = video_path
        captured["frame_pool_manifest"] = ctx.settings.frame_pool_manifest
        return original_run_pipeline_ctx(
            srt_path=srt_path,
            video_path=video_path,
            ctx=ctx,
            narrator=fake_narrator,
            **kwargs,
        )

    saved = ws.run_pipeline_ctx
    ws.run_pipeline_ctx = fake_run_pipeline_ctx

    try:
        payload = run_full_workflow(
            resolved_context=resolved_context,
        )
    finally:
        ws.run_pipeline_ctx = saved

    assert payload["workflowArtifacts"]["videoPath"] == str(video)
    assert payload["workflowArtifacts"]["srtPath"] == str(srt)
    validate_workflow_artifacts_dict(payload["workflowArtifacts"])
    assert captured["video_path"] == str(video)
    assert captured["frame_pool_manifest"] == str(pool_dir / "manifest.jsonl")
    artifacts = payload["workflowArtifacts"]
    assert artifacts.get("studyCardsHtmlPath")
    assert Path(artifacts["studyCardsHtmlPath"]).name == "demo.study_cards.html"
    assert artifacts.get("studyCardsHtmlError") is None
    study_html_path = Path(artifacts["studyCardsHtmlPath"])
    assert study_html_path.is_file()
    study_html = study_html_path.read_text(encoding="utf-8")
    assert study_html.startswith("<!DOCTYPE html>")
    assert "segment-card" in study_html


def test_run_full_workflow_owns_logging_lifecycle(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    srt = tmp_path / "demo.extracted.srt"
    srt.write_text(_SINGLE_GAP_SRT, encoding="utf-8")
    pool_dir = tmp_path / "demo.frame_pool"
    pool_dir.mkdir()
    (pool_dir / "manifest.jsonl").write_text("", encoding="utf-8")
    ctx_dir = tmp_path / "demo.subtitle_context"
    ctx_dir.mkdir()
    (ctx_dir / "chunks.jsonl").write_text("", encoding="utf-8")

    import numpy as np

    np.save(ctx_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))

    log_path = tmp_path / "workflow.jsonl"
    settings = make_settings(
        logging={
            "enabled": True,
            "level": "INFO",
            "format": "jsonl",
            "stderr": False,
            "file": str(log_path),
        }
    )
    request = WorkflowRequest(
        video_path=str(video),
        output_root=str(tmp_path),
        user_id="user-1",
    )
    resolved_context = resolved_run_context_from_request(
        request=request,
        settings=settings,
    )
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=replace(
                resolved_context.execution,
                pipeline=replace(
                    resolved_context.execution.pipeline,
                    video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                ),
            ),
        )
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    run_full_workflow(resolved_context=resolved_context, narrator=fake_narrator)

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    events = [row["event"] for row in rows]
    assert events.count("workflow.start") == 1
    assert events.count("workflow.done") == 1
    assert "subtitle_extraction.done" in events
    assert "frame_pool.done" in events
    assert "subtitle_context.done" in events
    assert "video_package.done" in events
    assert "workflow_export.done" in events
    assert any(row.get("event") == "segment.start" and row.get("job_id") == "user-1" for row in rows)
    job = read_job_record(tmp_path / "workflow.json")
    assert job.job_id == "user-1"
    assert job.status == "succeeded"
    assert job.input_video_path == str(video)
    assert job.artifacts["videoPath"] == str(video)
    assert job.progress["status"] == "succeeded"


def test_run_full_workflow_writes_failed_workflow_manifest(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    settings = make_settings()
    request = WorkflowRequest(video_path=str(video), output_root=str(tmp_path), user_id="user-fail")
    resolved_context = resolved_run_context_from_request(request=request, settings=settings)
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=replace(
                resolved_context.execution,
                extract_subtitles=False,
            ),
        )
    )

    with pytest.raises(FileNotFoundError):
        run_full_workflow(resolved_context=resolved_context)

    job = read_job_record(tmp_path / "workflow.json")
    assert job.job_id == "user-fail"
    assert job.status == "failed"
    assert job.error is not None
    assert job.error["error_code"] == "artifact_missing"


def test_run_pipeline_ctx_requires_explicit_frame_source_options():
    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory

    settings = make_settings()
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=None,
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(_SINGLE_GAP_SRT, encoding="utf-8")
        try:
            run_pipeline_ctx(
                srt_path=str(srt),
                video_path="demo.mp4",
                ctx=ctx,
                narrator=fake_narrator,
            )
        except ValueError as exc:
            assert "frame_source_options is required" in str(exc)
        else:
            raise AssertionError("run_pipeline_ctx should require explicit frame_source_options")


def test_run_pipeline_ctx_detects_default_subtitle_context_index_dir():
    raw = _SINGLE_GAP_SRT

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=settings_to_frame_source_options(settings),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        index_dir = Path(tmp) / "demo.subtitle_context"
        index_dir.mkdir()
        (index_dir / "chunks.jsonl").write_text("", encoding="utf-8")
        import numpy as np

        np.save(index_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            narrator=fake_narrator,
        )
    assert payload["subtitleContextIndexDir"] == str(index_dir)


def test_run_pipeline_ctx_ignores_incomplete_default_subtitle_context_index_dir():
    raw = _SINGLE_GAP_SRT

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        frame_source_options=settings_to_frame_source_options(settings),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        index_dir = Path(tmp) / "demo.subtitle_context"
        index_dir.mkdir()
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            narrator=fake_narrator,
        )
    assert payload["subtitleContextIndexDir"] is None


def test_run_pipeline_ctx_can_polish_output():
    raw = _SINGLE_GAP_SRT

    class FakePolishResult:
        polished_text = "short line"
        segment_duration_sec = 1.0
        target_duration_sec = 0.8
        safety_margin_sec = 0.2
        speaking_rate_wpm = 150
        target_word_count = 2
        original_word_count = 6
        polished_word_count = 2
        estimated_original_duration_sec = 2.4
        estimated_polished_duration_sec = 0.8
        cefr_level = "A1"
        strength = "strong"
        provider = "openai"
        model = "gpt-4.1-mini"
        timing_api_sec = 0.12

    vocab_study_card = {
        "passage_id": "seg",
        "highlights_count": 1,
        "data": [
            {
                "match_text": "line",
                "word_root": "line",
                "pos": "n.",
                "definition": "线",
                "note": "",
            }
        ],
        "full_translation": "短句。",
    }

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("longer narration line here", end_sec - start_sec)

    def fake_polisher(text, duration_sec, **kwargs):
        assert text == "longer narration line here"
        assert duration_sec == 1.0
        assert kwargs["options"].prompt_style == "documentary"
        return FakePolishResult()

    def fake_vocab_generator(passage, **kwargs):
        assert passage == "longer narration line here"
        assert kwargs["cefr_level"] == "A1"
        return vocab_study_card, 0.01

    from tempfile import TemporaryDirectory
    settings = make_settings(narration_polish_enabled=True)
    pipeline_options = NarrationPipelineConfig(
        video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
        narration_options=settings.narration_options(),
        polish_options=settings.narration_polish_options(),
        frame_source_options=settings_to_frame_source_options(settings),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_options)

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        import movie_pipeline.pipeline as pipeline_module

        original_vocab_generator = pipeline_module.generate_vocab_study_card
        pipeline_module.generate_vocab_study_card = fake_vocab_generator
        try:
            payload = run_pipeline_ctx(
                srt_path=str(srt),
                video_path="demo.mp4",
                ctx=ctx,
                narrator=fake_narrator,
                polisher=fake_polisher,
            )
        finally:
            pipeline_module.generate_vocab_study_card = original_vocab_generator
    seg = payload["narratedSegments"][0]
    assert seg["text"] == "longer narration line here"
    assert seg["speechText"] == "short line"
    assert seg["polish"]["fitsDuration"] is True
    assert seg["polish"]["cefrLevel"] == "A1"
    assert seg["polish"]["sceneTitleZh"] is None
    assert seg["studyCard"]["vocab"]["highlights_count"] == 1
    assert seg["studyCard"]["vocab"]["data"][0]["match_text"] == "line"


def test_run_pipeline_ctx_can_synthesize_speech():
    raw = _SINGLE_GAP_SRT

    class FakeSpeechResult:
        text = "short line"
        audio_path = "/tmp/segment_001.mp3"
        metadata_path = "/tmp/segment_001.mp3.jsonl"
        segment_duration_sec = 1.0
        target_duration_sec = 0.8
        raw_duration_sec = 0.92
        audio_duration_sec = 0.79
        provider = "edge_tts"
        voice = "en-US-EmmaMultilingualNeural"
        rate = "+0%"
        volume = "+0%"
        pitch = "+0Hz"
        boundary = "SentenceBoundary"
        fit_applied = True
        timing_tts_sec = 0.3
        timing_fit_sec = 0.1

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("short line", end_sec - start_sec)

    def fake_synthesizer(text, duration_sec, **kwargs):
        assert text == "short line"
        assert duration_sec == 1.0
        assert kwargs["target_duration_sec"] == 1.0
        assert kwargs["options"].voice == "en-US-EmmaMultilingualNeural"
        return FakeSpeechResult()

    from tempfile import TemporaryDirectory
    settings = make_settings(
        gateway={"default_provider": "newapi"},
        api_keys={"newapi": "sk-test"},
        api_providers={"newapi": "https://example.test/v1"},
        model_defaults={"narration": "gpt-4o-mini", "tts": "qwen3-tts-flash"},
        narration_tts_enabled=True,
        tts_defaults={"voice": "en-US-EmmaMultilingualNeural"},
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        ctx = RunContext(
            settings=settings,
            pipeline=NarrationPipelineConfig(
                video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                min_gap_sec=0.5,
                subtitle_guard_sec=0.25,
                narration_options=settings.narration_options(),
                speech_options=settings.narration_speech_options(),
                frame_source_options=settings_to_frame_source_options(settings),
            ),
        )
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            speech_output_dir=str(Path(tmp) / "speech"),
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
        )
    seg = payload["narratedSegments"][0]
    assert seg["speech"]["audioPath"].endswith(".mp3")
    assert seg["speech"]["fitApplied"] is True
    assert seg["speech"]["fitsDuration"] is True


def test_render_video_from_narration_payload_can_render_video():
    raw = _SINGLE_GAP_SRT

    class FakeSpeechResult:
        text = "short line"
        audio_path = "/tmp/segment_001.mp3"
        metadata_path = "/tmp/segment_001.mp3.jsonl"
        segment_duration_sec = 1.0
        target_duration_sec = 1.0
        raw_duration_sec = 0.9
        audio_duration_sec = 0.9
        provider = "edge_tts"
        voice = "en-US-EmmaMultilingualNeural"
        rate = "+0%"
        volume = "+0%"
        pitch = "+0Hz"
        boundary = "SentenceBoundary"
        fit_applied = False
        timing_tts_sec = 0.3
        timing_fit_sec = None

    class FakeRenderResult:
        video_path = "demo.mp4"
        output_path = "demo.narrated.mp4"
        segment_count = 1
        video_duration_sec = 4.0
        background_audio_volume = 0.35
        speech_audio_volume = 1.0
        subtitle_srt_path = None
        timing_render_sec = 0.5

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("short line", end_sec - start_sec)

    def fake_synthesizer(text, duration_sec, **kwargs):
        return FakeSpeechResult()

    def fake_renderer(video_path, segments, **kwargs):
        assert video_path == "demo.mp4"
        assert len(segments) == 1
        assert segments[0].audio_path.endswith(".mp3")
        assert kwargs["options"].speech_audio_volume == 1.0
        return FakeRenderResult()

    from tempfile import TemporaryDirectory
    settings = make_settings(
        narration_tts_enabled=True,
        narration_video_background_audio_volume=0.35,
        narration_video_speech_audio_volume=1.0,
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        ctx = RunContext(
            settings=settings,
            pipeline=NarrationPipelineConfig(
                video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                min_gap_sec=0.5,
                subtitle_guard_sec=0.25,
                narration_options=settings.narration_options(),
                speech_options=settings.narration_speech_options(),
                video_options=settings.narration_video_options(),
                frame_source_options=settings_to_frame_source_options(settings),
            ),
        )
        payload = run_pipeline_ctx(
            srt_path=str(srt),
            video_path="demo.mp4",
            ctx=ctx,
            speech_output_dir=str(Path(tmp) / "speech"),
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
        )
        rendered = render_video_from_narration_payload(
            payload=payload,
            video_path=Path("demo.mp4"),
            output_path=Path(tmp) / "demo.narrated.mp4",
            subtitle_srt_path=None,
            settings=settings,
            video_renderer=fake_renderer,
        )
    assert rendered["renderedVideo"]["outputPath"] == "demo.narrated.mp4"


def test_resolve_workflow_config_applies_tier_defaults_without_product_request():
    settings = make_settings(default_prompt_style="documentary")
    request = WorkflowRequest(
        video_path="demo.mp4",
        user_tier="pro",
        prompt_style="movie_commentary",
        cefr_level="A1",
        enable_speech=True,
        enable_embed_video=True,
    )
    resolved = resolve_workflow_config(
        request=request,
        settings=settings,
    )
    execution = resolved.execution
    assert execution.build_subtitle_context is True
    assert execution.enable_polish is True
    assert execution.enable_speech is True
    assert execution.enable_embed_video is True
    assert execution.pipeline.narration_options.prompt_style == "movie_commentary"
    assert execution.pipeline.polish_options is not None
    assert execution.pipeline.polish_options.cefr_level == "A1"


def test_run_full_workflow_reuses_existing_artifacts_and_runs_pipeline(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    srt = tmp_path / "demo.extracted.srt"
    srt.write_text(
        _SINGLE_GAP_SRT,
        encoding="utf-8",
    )
    pool_dir = tmp_path / "demo.frame_pool"
    pool_dir.mkdir()
    (pool_dir / "manifest.jsonl").write_text("", encoding="utf-8")
    ctx_dir = tmp_path / "demo.subtitle_context"
    ctx_dir.mkdir()
    (ctx_dir / "chunks.jsonl").write_text("", encoding="utf-8")
    import numpy as np

    np.save(ctx_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))

    settings = make_settings()

    execution = ResolvedExecutionConfig(
        extract_subtitles=True,
        build_frame_pool=True,
        build_subtitle_context=True,
        enable_polish=False,
        enable_speech=False,
        enable_embed_video=False,
        output_root=str(tmp_path),
        subtitle_extraction_options=settings.subtitle_extraction_options(),
        frame_pool_build_options=settings.frame_pool_build_options(),
        subtitle_context_build_options=settings.subtitle_context_build_options(),
        pipeline=NarrationPipelineConfig(
            video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
            min_gap_sec=1.0,
            subtitle_guard_sec=0.25,
            ffprobe_bin="ffprobe",
            narration_options=settings.narration_options(),
            frame_source_options=settings_to_frame_source_options(settings),
            subtitle_context_build_options=settings.subtitle_context_build_options(),
            subtitle_context_retrieve_options=settings.subtitle_context_retrieve_options(),
            polish_options=None,
            speech_options=None,
            video_options=None,
        ),
    )
    resolved_context = resolved_run_context_from_request(
        request=WorkflowRequest(video_path=str(video), output_root=str(tmp_path)),
        settings=settings,
    )
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=execution,
        )
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    import movie_pipeline.workflow_stages as ws

    original_run_pipeline_ctx = ws.run_pipeline_ctx
    captured = {}

    def fake_run_pipeline_ctx(*, srt_path, video_path, ctx, narrator=None, **kwargs):
        captured["frame_pool_manifest"] = ctx.settings.frame_pool_manifest
        return original_run_pipeline_ctx(
            srt_path=srt_path,
            video_path=video_path,
            ctx=ctx,
            narrator=fake_narrator,
            **kwargs,
        )

    saved = ws.run_pipeline_ctx
    ws.run_pipeline_ctx = fake_run_pipeline_ctx

    try:
        payload = run_full_workflow(
            resolved_context=resolved_context,
        )
    finally:
        ws.run_pipeline_ctx = saved

    assert payload["workflowArtifacts"]["srtPath"] == str(srt)
    assert payload["workflowArtifacts"]["framePoolManifest"] == str(pool_dir / "manifest.jsonl")
    assert payload["workflowArtifacts"]["subtitleContextIndexDir"] == str(ctx_dir)
    validate_workflow_artifacts_dict(payload["workflowArtifacts"])
    assert payload["narratedSegments"][0]["text"] == "narration"
    assert captured["frame_pool_manifest"] == str(pool_dir / "manifest.jsonl")
    artifacts = payload["workflowArtifacts"]
    assert artifacts.get("studyCardsHtmlPath")
    assert Path(artifacts["studyCardsHtmlPath"]).name == "demo.study_cards.html"
    assert artifacts.get("studyCardsHtmlError") is None
    assert Path(artifacts["studyCardsHtmlPath"]).is_file()
    study_body = Path(artifacts["studyCardsHtmlPath"]).read_text(encoding="utf-8")
    assert "segment-card" in study_body
