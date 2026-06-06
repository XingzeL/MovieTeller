from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from movie_pipeline.job_runner.quota_clip import (
    clip_video_to_processed,
    should_clip_video,
)


def test_should_clip_video_when_end_point_set() -> None:
    assert should_clip_video(start_point=0, end_point=30, source_path=__file__) is True


def test_should_not_clip_without_end_point() -> None:
    assert should_clip_video(start_point=None, end_point=None, source_path=__file__) is False


def test_clip_video_to_processed_uses_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    output = tmp_path / "processed.mp4"

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        output.write_bytes(b"processed")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clip_video_to_processed(
        source_path=source,
        output_path=output,
        start_point=0,
        end_point=45,
        ffmpeg_bin="ffmpeg",
    )
    assert result == output
    assert calls
    duration_arg = calls[0][calls[0].index("-t") + 1]
    assert float(duration_arg) == 45.0
