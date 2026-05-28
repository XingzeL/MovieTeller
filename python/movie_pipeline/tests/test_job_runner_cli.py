from __future__ import annotations

import json
from pathlib import Path

from movie_pipeline.job_runner.cli import main
from movie_pipeline.job_runner.request_io import workflow_request_from_api_dict
from movie_pipeline.job import read_job_record


def test_workflow_request_from_api_dict_maps_camel_case() -> None:
    req = workflow_request_from_api_dict(
        {
            "enablePolish": False,
            "enableSpeech": True,
            "cefrLevel": "B1",
            "minGapSec": 1.5,
            "ttsVoice": "Cherry",
            "ttsLanguage": "zh",
            "sourceLanguage": "ja",
        },
        video_path="/tmp/video.mp4",
    )
    assert req.video_path == "/tmp/video.mp4"
    assert req.enable_polish is False
    assert req.enable_speech is True
    assert req.cefr_level == "B1"
    assert req.min_gap_sec == 1.5
    assert req.tts_voice == "Cherry"
    assert req.tts_language == "zh"
    assert req.source_language == "ja"


def test_job_runner_cli_writes_failed_manifest(tmp_path, monkeypatch) -> None:
    jobs_root = tmp_path / "jobs"
    video = tmp_path / "input.mp4"
    video.write_bytes(b"x")
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({"enablePolish": False}), encoding="utf-8")

    monkeypatch.setattr(
        "movie_pipeline.job_runner.cli.load_settings",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
    )

    code = main(
        [
            "--job-id",
            "job-fail",
            "--jobs-root",
            str(jobs_root),
            "--video",
            str(video),
            "--request-json",
            str(request_path),
        ]
    )
    assert code == 1
    record = read_job_record(jobs_root / "job-fail" / "workflow.json")
    assert record.status == "failed"
    assert record.error is not None
    assert record.error.get("error_message")
