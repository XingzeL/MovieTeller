from subtitle_extraction.parse_srt import parse_srt_text


def test_parse_srt_basic():
    raw = """1
00:00:01,000 --> 00:00:03,500
Hello world

2
00:00:04,000 --> 00:00:05,000
Second line
"""
    cues = parse_srt_text(raw)
    assert len(cues) == 2
    assert cues[0].start_sec == 1.0
    assert cues[0].end_sec == 3.5
    assert cues[0].text == "Hello world"
    assert cues[1].text == "Second line"


def test_parse_srt_multiline_and_bom():
    raw = "\ufeff2\n00:00:00,000 --> 00:00:02,000\nLine one\nLine two\n\n"
    cues = parse_srt_text(raw)
    assert len(cues) == 1
    assert cues[0].text == "Line one Line two"


def test_parse_srt_skips_invalid():
    raw = """1
bad timestamp --> 00:00:01,000
x

2
00:00:01,000 --> 00:00:02,000
ok
"""
    cues = parse_srt_text(raw)
    assert len(cues) == 1
    assert cues[0].text == "ok"
