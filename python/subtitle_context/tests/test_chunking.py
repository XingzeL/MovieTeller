from pipeline_types import SubtitleCue

from subtitle_context.chunking import chunk_subtitle_cues


def test_chunk_subtitle_cues_sliding_windows():
    cues = [
        SubtitleCue(start_sec=0.0, end_sec=1.0, text="a"),
        SubtitleCue(start_sec=1.0, end_sec=2.0, text="b"),
        SubtitleCue(start_sec=2.0, end_sec=3.0, text="c"),
        SubtitleCue(start_sec=3.0, end_sec=4.0, text="d"),
        SubtitleCue(start_sec=4.0, end_sec=5.0, text="e"),
    ]
    chunks = chunk_subtitle_cues(cues, cue_count=3, stride=2)
    assert [chunk.chunk_id for chunk in chunks] == ["000001", "000002", "000003"]
    assert chunks[0].text == "a b c"
    assert chunks[1].text == "c d e"
    assert chunks[2].text == "e"
    assert chunks[1].start_sec == 2.0
    assert chunks[1].end_sec == 5.0
