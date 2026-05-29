from __future__ import annotations

from pathlib import Path

import pytest

from movie_pipeline.cancel_check import (
    JobCanceledError,
    ensure_not_canceled,
    ensure_not_canceled_for_output_root,
    is_job_canceled,
    job_root_from_speech_output_dir,
)


def test_is_job_canceled_reads_cancel_flag(tmp_path: Path) -> None:
    job_root = tmp_path / "job-1"
    job_root.mkdir()
    assert is_job_canceled(job_root) is False
    (job_root / "cancel.flag").write_text("2026-01-01T00:00:00Z\n", encoding="utf-8")
    assert is_job_canceled(job_root) is True


def test_job_root_from_speech_output_dir_typical_layout(tmp_path: Path) -> None:
    job_root = tmp_path / "job-2"
    speech_audio = job_root / "speech" / "audio"
    speech_audio.mkdir(parents=True)
    assert job_root_from_speech_output_dir(speech_audio) == job_root.resolve()


def test_ensure_not_canceled_via_speech_dir(tmp_path: Path) -> None:
    job_root = tmp_path / "job-3"
    speech_audio = job_root / "speech" / "audio"
    speech_audio.mkdir(parents=True)
    (job_root / "cancel.flag").write_text("x\n", encoding="utf-8")
    with pytest.raises(JobCanceledError):
        ensure_not_canceled(speech_output_dir=str(speech_audio))


def test_ensure_not_canceled_for_output_root(tmp_path: Path) -> None:
    job_root = tmp_path / "job-4"
    job_root.mkdir()
    (job_root / "cancel.flag").write_text("x\n", encoding="utf-8")
    with pytest.raises(JobCanceledError):
        ensure_not_canceled_for_output_root(job_root)
