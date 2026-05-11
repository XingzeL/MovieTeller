from media_utils import ffprobe_path_for, probe_duration_sec, segment_duration_sec


class FakeProc:
    def __init__(self, *, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ffprobe_path_for_uses_sibling_binary():
    assert ffprobe_path_for("/opt/homebrew/bin/ffmpeg") == "/opt/homebrew/bin/ffprobe"
    assert ffprobe_path_for("custom-ffmpeg") == "ffprobe"


def test_probe_duration_sec_reads_float_duration(tmp_path):
    media = tmp_path / "demo.mp4"
    media.write_bytes(b"x")

    def fake_run(cmd, capture_output, text, check):
        assert cmd[0] == "ffprobe"
        return FakeProc(stdout="12.34\n")

    assert probe_duration_sec(
        str(media),
        ffprobe_bin="ffprobe",
        subprocess_run=fake_run,
    ) == 12.34


def test_segment_duration_sec_uses_full_probe_when_bounds_absent(tmp_path):
    media = tmp_path / "demo.mp4"
    media.write_bytes(b"x")

    def fake_run(cmd, capture_output, text, check):
        return FakeProc(stdout="8.50\n")

    assert segment_duration_sec(
        str(media),
        None,
        None,
        ffprobe_bin="ffprobe",
        subprocess_run=fake_run,
    ) == 8.5


def test_segment_duration_sec_uses_bounds_when_present():
    assert segment_duration_sec(
        "ignored.mp4",
        2.0,
        5.5,
        ffprobe_bin="ffprobe",
    ) == 3.5
