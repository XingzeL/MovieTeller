from pathlib import Path
from unittest import mock

from subtitle_extraction.transcribe import (
    TranscriptionError,
    build_transcribe_command,
    extract_subtitles,
)


def test_build_transcribe_command():
    cmd = build_transcribe_command(
        executable="/bin/vc",
        input_path="/a/v.mp4",
        output_srt_path="/a/v.srt",
        asr="bijian",
        language="auto",
    )
    assert cmd[:2] == ["/bin/vc", "transcribe"]
    assert "--asr" in cmd and "bijian" in cmd
    assert "--quiet" in cmd


def test_extract_subtitles_missing_input():
    try:
        extract_subtitles("/nonexistent/video.mp4", videocaptioner_bin="/bin/false")
    except TranscriptionError as e:
        assert "not found" in str(e)
    else:
        raise AssertionError("expected TranscriptionError")


def test_extract_subtitles_bad_asr():
    try:
        extract_subtitles(__file__, asr="invalid-engine")
    except TranscriptionError as e:
        assert "Unsupported" in str(e)
    else:
        raise AssertionError("expected TranscriptionError")


def test_extract_subtitles_propagates_exit_code():
    def fake_run(cmd, capture_output, text, timeout):
        class P:
            returncode = 7
            stderr = "boom"

        return P()

    with mock.patch("subtitle_extraction.transcribe.resolve_videocaptioner_bin", return_value="/vc"):
        try:
            extract_subtitles(
                __file__,
                videocaptioner_bin="/vc",
                output_srt_path=str(Path(__file__).with_suffix(".tmp.srt")),
                subprocess_run=fake_run,
            )
        except TranscriptionError as e:
            assert e.exit_code == 7
            assert "boom" in e.stderr
        else:
            raise AssertionError("expected TranscriptionError")
