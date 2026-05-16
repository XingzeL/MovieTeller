from pathlib import Path

from frame_source import FrameSourceOptions
from movieteller_config.schema import settings_from_dict

from movie_pipeline import (
    MoviePipelineOptions,
    parse_product_request,
    run_full_workflow,
    narrate_analysis_candidates,
    run_pipeline,
    translate_product_request_to_workflow_options,
)
from subtitle_analysis import analyze_srt_text


def settings_to_frame_source_options(settings):
    return FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
        allow_uniform_fallback=True,
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
        video_path="demo.mp4",
        max_candidates=2,
        narration_options=settings.narration_options(prompt_style="documentary"),
        frame_source_options=frame_source_options,
        narrator=fake_narrator,
        settings=settings,
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
        video_duration_sec=8.0,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.25,
    )
    settings = make_settings()
    frame_source_options = settings_to_frame_source_options(settings)
    calls = []

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        calls.append(kwargs["narration_context"])
        return ("narration", end_sec - start_sec)

    segments = narrate_analysis_candidates(
        analysis,
        video_path="demo.mp4",
        subtitle_context_index_dir="demo.subtitle_context",
        max_candidates=1,
        narration_options=settings.narration_options(),
        frame_source_options=frame_source_options,
        narrator=fake_narrator,
        settings=settings,
    )
    assert len(segments) == 1
    assert calls[0].prev_subtitle_text == "a"
    assert calls[0].next_subtitle_text == "b"
    assert calls[0].retrieved_context_texts == ()


def test_run_pipeline_returns_timed_json_payload():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=4.0,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.0,
        max_candidates=1,
        narration_options=settings.narration_options(),
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=pipeline_options,
            narrator=fake_narrator,
            settings=settings,
        )
    assert "narratedSegments" in payload
    assert len(payload["narratedSegments"]) == 1
    assert payload["narratedSegments"][0]["text"] == "narration"
    assert payload["narratedSegments"][0]["speechText"] == "narration"


def test_run_pipeline_detects_default_subtitle_context_index_dir():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=4.0,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.0,
        max_candidates=1,
        narration_options=settings.narration_options(),
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        index_dir = Path(tmp) / "demo.subtitle_context"
        index_dir.mkdir()
        (index_dir / "chunks.jsonl").write_text("", encoding="utf-8")
        import numpy as np

        np.save(index_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=pipeline_options,
            narrator=fake_narrator,
            settings=settings,
        )
    assert payload["subtitleContextIndexDir"] == str(index_dir)


def test_run_pipeline_ignores_incomplete_default_subtitle_context_index_dir():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory
    settings = make_settings()
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=4.0,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.0,
        max_candidates=1,
        narration_options=settings.narration_options(),
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        index_dir = Path(tmp) / "demo.subtitle_context"
        index_dir.mkdir()
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=pipeline_options,
            narrator=fake_narrator,
            settings=settings,
        )
    assert payload["subtitleContextIndexDir"] is None


def test_run_pipeline_can_polish_output():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

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

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("longer narration line here", end_sec - start_sec)

    def fake_polisher(text, duration_sec, **kwargs):
        assert text == "longer narration line here"
        assert duration_sec == 1.0
        assert kwargs["options"].prompt_style == "documentary"
        return FakePolishResult()

    from tempfile import TemporaryDirectory
    settings = make_settings(narration_polish_enabled=True)
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=4.0,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.0,
        max_candidates=1,
        narration_options=settings.narration_options(),
        polish_options=settings.narration_polish_options(),
    )

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=pipeline_options,
            narrator=fake_narrator,
            polisher=fake_polisher,
            settings=settings,
        )
    seg = payload["narratedSegments"][0]
    assert seg["text"] == "longer narration line here"
    assert seg["speechText"] == "short line"
    assert seg["polish"]["fitsDuration"] is True
    assert seg["polish"]["cefrLevel"] == "A1"


def test_run_pipeline_can_synthesize_speech():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

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
        assert kwargs["options"].provider_slug == "newapi"
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
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=MoviePipelineOptions(
                video_duration_sec=4.0,
                min_gap_sec=0.5,
                subtitle_guard_sec=0.0,
                max_candidates=1,
                speech_output_dir=str(Path(tmp) / "speech"),
                narration_options=settings.narration_options(),
                speech_options=settings.narration_speech_options(),
            ),
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
            settings=settings,
        )
    seg = payload["narratedSegments"][0]
    assert seg["speech"]["audioPath"].endswith(".mp3")
    assert seg["speech"]["fitApplied"] is True
    assert seg["speech"]["fitsDuration"] is True


def test_run_pipeline_can_render_video():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

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
        payload = run_pipeline(
            srt_path=str(srt),
            video_path="demo.mp4",
            pipeline_options=MoviePipelineOptions(
                video_duration_sec=4.0,
                min_gap_sec=0.5,
                subtitle_guard_sec=0.0,
                max_candidates=1,
                speech_output_dir=str(Path(tmp) / "speech"),
                embed_video=True,
                narration_options=settings.narration_options(),
                speech_options=settings.narration_speech_options(),
                video_options=settings.narration_video_options(),
            ),
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
            video_renderer=fake_renderer,
            settings=settings,
        )
    assert payload["renderedVideo"]["outputPath"] == "demo.narrated.mp4"


def test_translate_product_request_to_workflow_options_applies_level_defaults():
    settings = make_settings(default_prompt_style="documentary")
    req = parse_product_request(
        {
            "level": "pro",
            "style": "movie_commentary",
            "cefrLevel": "A1",
            "enableSpeech": True,
            "enableEmbedVideo": True,
            "maxCandidates": 2,
        }
    )
    options = translate_product_request_to_workflow_options(req, settings)
    assert options.build_subtitle_context is True
    assert options.enable_polish is True
    assert options.enable_speech is True
    assert options.enable_embed_video is True
    assert options.movie_pipeline_options is not None
    assert options.movie_pipeline_options.max_candidates == 2
    assert options.movie_pipeline_options.narration_options.prompt_style == "movie_commentary"
    assert options.movie_pipeline_options.polish_options is not None
    assert options.movie_pipeline_options.polish_options.cefr_level == "A1"


def test_run_full_workflow_reuses_existing_artifacts_and_runs_pipeline(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    srt = tmp_path / "demo.extracted.srt"
    srt.write_text(
        """1
00:00:01,000 --> 00:00:02,000
x
""",
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

    from movie_pipeline.full_workflow import workflow_options_from_settings

    options = workflow_options_from_settings(settings, output_root=str(tmp_path))
    assert options.movie_pipeline_options is not None
    options = type(options)(
        extract_subtitles=options.extract_subtitles,
        build_frame_pool=options.build_frame_pool,
        build_subtitle_context=options.build_subtitle_context,
        enable_polish=False,
        enable_speech=options.enable_speech,
        enable_embed_video=options.enable_embed_video,
        output_root=options.output_root,
        subtitle_extraction_options=options.subtitle_extraction_options,
        frame_pool_build_options=options.frame_pool_build_options,
        subtitle_context_build_options=options.subtitle_context_build_options,
        movie_pipeline_options=MoviePipelineOptions(
            video_duration_sec=4.0,
            min_gap_sec=options.movie_pipeline_options.min_gap_sec,
            subtitle_guard_sec=options.movie_pipeline_options.subtitle_guard_sec,
            ffprobe_bin=options.movie_pipeline_options.ffprobe_bin,
            max_candidates=options.movie_pipeline_options.max_candidates,
            subtitle_context_index_dir=options.movie_pipeline_options.subtitle_context_index_dir,
            build_subtitle_context=options.movie_pipeline_options.build_subtitle_context,
            speech_output_dir=options.movie_pipeline_options.speech_output_dir,
            embed_video=options.movie_pipeline_options.embed_video,
            embed_output_path=options.movie_pipeline_options.embed_output_path,
            narration_options=options.movie_pipeline_options.narration_options,
            frame_source_options=options.movie_pipeline_options.frame_source_options,
            subtitle_context_build_options=options.movie_pipeline_options.subtitle_context_build_options,
            subtitle_context_retrieve_options=options.movie_pipeline_options.subtitle_context_retrieve_options,
            polish_options=None,
            speech_options=None,
            video_options=None,
        ),
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from movie_pipeline import full_workflow as fw

    original_run_pipeline = fw.run_pipeline
    captured = {}

    def fake_run_pipeline(*, srt_path, video_path, pipeline_options, settings):
        captured["frame_pool_manifest"] = settings.frame_pool_manifest
        return original_run_pipeline(
            srt_path=srt_path,
            video_path=video_path,
            pipeline_options=pipeline_options,
            settings=settings,
            narrator=fake_narrator,
        )

    import movie_pipeline.full_workflow as full_workflow_module

    saved = full_workflow_module.run_pipeline
    full_workflow_module.run_pipeline = fake_run_pipeline

    try:
        payload = run_full_workflow(
            video_path=str(video),
            options=options,
            settings=settings,
        )
    finally:
        full_workflow_module.run_pipeline = saved

    assert payload["workflowArtifacts"]["srtPath"] == str(srt)
    assert payload["workflowArtifacts"]["framePoolManifest"] == str(pool_dir / "manifest.jsonl")
    assert payload["workflowArtifacts"]["subtitleContextIndexDir"] == str(ctx_dir)
    assert payload["narratedSegments"][0]["text"] == "narration"
    assert captured["frame_pool_manifest"] == str(pool_dir / "manifest.jsonl")
