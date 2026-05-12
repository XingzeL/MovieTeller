from pathlib import Path

import subtitle_analysis
from subtitle_analysis import analyze_srt_text


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


def test_subtitle_analysis_exports_analysis_only_api():
    assert "analyze_and_narrate" not in subtitle_analysis.__all__
    assert "narrate_analysis_candidates" not in subtitle_analysis.__all__
