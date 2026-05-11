from pipeline_types import (
    FrameBatch,
    NarrationAudioSegment,
    NarrationCandidate,
    NarrationContext,
    NarrationResult,
    SubtitleCue,
)


def test_subtitle_cue_fields():
    cue = SubtitleCue(start_sec=1.0, end_sec=2.0, text="hello")
    assert cue.text == "hello"


def test_narration_candidate_duration():
    seg = NarrationCandidate(
        start_sec=2.5,
        end_sec=5.0,
        prev_subtitle_text="a",
        next_subtitle_text="b",
    )
    assert seg.duration_sec == 2.5


def test_frame_batch_fields():
    batch = FrameBatch(
        frames_base64_png=("abc",),
        frame_times_sec=(1.25,),
        duration_sec=3.0,
        source="uniform",
        shot_ids=None,
    )
    assert batch.source == "uniform"


def test_narration_context_and_result_fields():
    ctx = NarrationContext(segment_start_sec=1.0, segment_end_sec=4.0)
    result = NarrationResult(
        text="demo",
        duration_sec=3.0,
        frame_count=4,
        frame_source="uniform",
    )
    assert ctx.segment_end_sec == 4.0
    assert result.frame_count == 4


def test_narration_audio_segment_duration():
    seg = NarrationAudioSegment(start_sec=1.0, end_sec=3.25, audio_path="a.mp3")
    assert seg.duration_sec == 2.25
