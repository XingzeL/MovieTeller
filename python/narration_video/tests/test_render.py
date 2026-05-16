from pathlib import Path

import pytest
from movieteller_config.schema import NarrationVideoOptions

from narration_video.render import render_narrated_video
from narration_video.types import NarrationAudioSegment


def test_render_narrated_video_requires_segments(tmp_path):
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    with pytest.raises(ValueError):
        render_narrated_video(
            str(video),
            [],
            output_path=str(tmp_path / "out.mp4"),
            options=NarrationVideoOptions(
                ffmpeg_bin="ffmpeg",
                background_audio_volume=0.35,
                speech_audio_volume=1.0,
            ),
        )


def test_render_narrated_video_builds_ffmpeg_command(monkeypatch, tmp_path):
    video = tmp_path / "demo.mp4"
    audio = tmp_path / "seg1.mp3"
    subtitle = tmp_path / "final.srt"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    commands = []

    def fake_probe_duration_sec(video_path, *, ffprobe_bin):
        return 5.0

    def fake_has_audio(*args, **kwargs):
        return True

    def fake_run(cmd, **kwargs):
        commands.append(cmd)

        class Proc:
            returncode = 0
            stderr = ""
            stdout = ""

        return Proc()

    monkeypatch.setattr("narration_video.render.probe_duration_sec", fake_probe_duration_sec)
    monkeypatch.setattr("narration_video.render._video_has_audio_stream", fake_has_audio)
    result = render_narrated_video(
        str(video),
        [NarrationAudioSegment(start_sec=1.25, end_sec=2.0, audio_path=str(audio))],
        output_path=str(tmp_path / "out.mp4"),
        subtitle_srt_path=str(subtitle),
        options=NarrationVideoOptions(
            ffmpeg_bin="ffmpeg",
            background_audio_volume=0.35,
            speech_audio_volume=1.0,
        ),
        subprocess_run=fake_run,
    )
    assert result.output_path.endswith("out.mp4")
    assert any("adelay=1250|1250" in part for part in commands[0])
    assert any(str(subtitle) == part for part in commands[0])
    assert any("mov_text" == part for part in commands[0])
    assert result.subtitle_srt_path == str(subtitle)
