from unittest.mock import MagicMock

from narration.frames import extract_frames_base64, split_png_blob


def test_split_png_two_streams(fake_concat_png_stdout):
    parts = split_png_blob(fake_concat_png_stdout)
    assert len(parts) == 2
    assert parts[0].startswith(b"\x89PNG\r\n\x1a\n")
    assert parts[1].startswith(b"\x89PNG\r\n\x1a\n")


def test_extract_frames_with_bounds_uses_ss_and_t(fake_concat_png_stdout, tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00")

    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, check):
        calls.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = fake_concat_png_stdout
        m.stderr = b""
        return m

    b64_list = extract_frames_base64(
        str(vid),
        start_sec=1.0,
        end_sec=5.0,
        duration_sec=4.0,
        max_frames=8,
        ffmpeg_bin="/bin/ffmpeg",
        max_edge_pixels=512,
        subprocess_run=fake_run,
    )
    assert len(b64_list) == 2
    cmd = calls[0]
    assert "-vf" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    assert "force_original_aspect_ratio=decrease" in vf
    assert "512:512" in vf
    assert "-ss" in cmd
    assert "-t" in cmd
    assert cmd[0] == "/bin/ffmpeg"


def test_extract_full_file_omits_ss(fake_concat_png_stdout, tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00")

    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, check):
        calls.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = fake_concat_png_stdout
        m.stderr = b""
        return m

    extract_frames_base64(
        str(vid),
        start_sec=None,
        end_sec=None,
        duration_sec=10.0,
        max_frames=4,
        ffmpeg_bin="ffmpeg",
        subprocess_run=fake_run,
    )
    assert "-ss" not in calls[0]
    vf = calls[0][calls[0].index("-vf") + 1]
    assert "768:768" in vf
