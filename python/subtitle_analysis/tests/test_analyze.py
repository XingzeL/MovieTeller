from pathlib import Path

from subtitle_analysis import analyze_srt_text
from subtitle_analysis.pipeline import analyze_and_narrate, narrate_analysis_candidates


def test_analyze_srt_internal_gaps_without_video_duration():
    raw = """1
00:00:01,000 --> 00:00:03,000
hello

2
00:00:06,000 --> 00:00:08,000
world
"""
    result = analyze_srt_text(raw, min_gap_sec=1.0, subtitle_guard_sec=0.25)
    assert len(result.subtitle_spans) == 2
    assert len(result.raw_gaps) == 2
    assert result.raw_gaps[0].start_sec == 0.0
    assert result.raw_gaps[0].end_sec == 1.0
    assert result.raw_gaps[1].start_sec == 3.0
    assert result.raw_gaps[1].end_sec == 6.0
    assert len(result.narration_candidates) == 1
    seg = result.narration_candidates[0]
    assert seg.start_sec == 3.25
    assert seg.end_sec == 5.75
    assert seg.prev_subtitle_text == "hello"
    assert seg.next_subtitle_text == "world"


def test_analyze_srt_with_trailing_gap_when_video_duration_known():
    raw = """1
00:00:00,000 --> 00:00:02,000
a

2
00:00:05,000 --> 00:00:06,000
b
"""
    result = analyze_srt_text(
        raw,
        video_duration_sec=10.0,
        min_gap_sec=1.0,
        subtitle_guard_sec=0.5,
    )
    assert len(result.raw_gaps) == 2
    assert result.raw_gaps[0].start_sec == 2.0
    assert result.raw_gaps[0].end_sec == 5.0
    assert result.raw_gaps[1].start_sec == 6.0
    assert result.raw_gaps[1].end_sec == 10.0
    assert len(result.narration_candidates) == 2
    assert result.narration_candidates[0].start_sec == 2.5
    assert result.narration_candidates[0].end_sec == 4.5
    assert result.narration_candidates[1].start_sec == 6.5
    assert result.narration_candidates[1].end_sec == 10.0


def test_overlapping_cues_are_merged_before_gap_analysis():
    raw = """1
00:00:00,000 --> 00:00:03,000
a

2
00:00:02,500 --> 00:00:05,000
b

3
00:00:08,000 --> 00:00:09,000
c
"""
    result = analyze_srt_text(
        raw,
        video_duration_sec=10.0,
        min_gap_sec=0.5,
        subtitle_guard_sec=0.25,
    )
    assert len(result.subtitle_spans) == 2
    assert result.subtitle_spans[0].start_sec == 0.0
    assert result.subtitle_spans[0].end_sec == 5.0
    assert len(result.raw_gaps) == 2
    assert result.raw_gaps[0].start_sec == 5.0
    assert result.raw_gaps[0].end_sec == 8.0


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

    calls = []

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        calls.append((video_path, start_sec, end_sec, kwargs["prompt_style"]))
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
        prompt_style="documentary",
        narrator=fake_narrator,
        settings=object(),
    )
    assert len(segments) == 2
    assert segments[0].narration_text.startswith("text-")
    assert segments[0].frame_count == 4
    assert calls[0][0] == "demo.mp4"


def test_analyze_and_narrate_returns_timed_json_payload():
    raw = """1
00:00:01,000 --> 00:00:02,000
x
"""

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = analyze_and_narrate(
            srt_path=str(srt),
            video_path="demo.mp4",
            video_duration_sec=4.0,
            min_gap_sec=0.5,
            subtitle_guard_sec=0.0,
            max_candidates=1,
            narrator=fake_narrator,
            settings=object(),
        )
    assert "narratedSegments" in payload
    assert len(payload["narratedSegments"]) == 1
    assert payload["narratedSegments"][0]["text"] == "narration"
    assert payload["narratedSegments"][0]["speechText"] == "narration"


def test_analyze_and_narrate_can_polish_output():
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
        return FakePolishResult()

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = analyze_and_narrate(
            srt_path=str(srt),
            video_path="demo.mp4",
            video_duration_sec=4.0,
            min_gap_sec=0.5,
            subtitle_guard_sec=0.0,
            max_candidates=1,
            narrator=fake_narrator,
            polisher=fake_polisher,
            polish=True,
            settings=object(),
        )
    seg = payload["narratedSegments"][0]
    assert seg["text"] == "longer narration line here"
    assert seg["speechText"] == "short line"
    assert seg["polish"]["fitsDuration"] is True
    assert seg["polish"]["cefrLevel"] == "A1"


def test_analyze_and_narrate_can_synthesize_speech():
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
        return FakeSpeechResult()

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = analyze_and_narrate(
            srt_path=str(srt),
            video_path="demo.mp4",
            video_duration_sec=4.0,
            min_gap_sec=0.5,
            subtitle_guard_sec=0.0,
            max_candidates=1,
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
            speech=True,
            speech_output_dir=str(Path(tmp) / "speech"),
            settings=object(),
        )
    seg = payload["narratedSegments"][0]
    assert seg["speech"]["audioPath"].endswith(".mp3")
    assert seg["speech"]["fitApplied"] is True
    assert seg["speech"]["fitsDuration"] is True


def test_analyze_and_narrate_can_render_video():
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
        return FakeRenderResult()

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        srt = Path(tmp) / "demo.srt"
        srt.write_text(raw, encoding="utf-8")
        payload = analyze_and_narrate(
            srt_path=str(srt),
            video_path="demo.mp4",
            video_duration_sec=4.0,
            min_gap_sec=0.5,
            subtitle_guard_sec=0.0,
            max_candidates=1,
            narrator=fake_narrator,
            synthesizer=fake_synthesizer,
            video_renderer=fake_renderer,
            embed_video=True,
            speech_output_dir=str(Path(tmp) / "speech"),
            settings=object(),
        )
    assert payload["renderedVideo"]["outputPath"] == "demo.narrated.mp4"
