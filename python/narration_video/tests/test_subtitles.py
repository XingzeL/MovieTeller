import json
from pathlib import Path

from narration_video.subtitles import build_subtitled_narration_srt


def test_build_subtitled_narration_srt_inserts_narration_cues(tmp_path):
    source_srt = tmp_path / "source.srt"
    source_srt.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n原台词一\n\n"
        "2\n00:00:05,000 --> 00:00:06,000\n原台词二\n",
        encoding="utf-8",
    )
    speech_json = tmp_path / "speech_video.json"
    speech_json.write_text(
        json.dumps(
            {
                "narratedSegments": [
                    {
                        "startSec": 2.0,
                        "endSec": 4.0,
                        "speech": {
                            "text": "旁白第一句。旁白第二句。",
                            "audioDurationSec": 2.0,
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_srt = tmp_path / "final.srt"

    result = build_subtitled_narration_srt(
        speech_video_json_path=str(speech_json),
        source_srt_path=str(source_srt),
        output_srt_path=str(output_srt),
    )

    text = output_srt.read_text(encoding="utf-8")
    assert "原台词一" in text
    assert "原台词二" in text
    assert "旁白第一句。" in text
    assert "旁白第二句。" in text
    assert result.inserted_cue_count == 2
    assert result.total_cue_count == 4
