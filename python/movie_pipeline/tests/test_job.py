from __future__ import annotations

from pathlib import Path

import pytest

from movie_pipeline.job import (
    JobPaths,
    JobRecord,
    JobStore,
    WorkflowArtifacts,
    job_record_from_dict,
    read_job_record,
    write_job_record,
    workflow_artifacts_from_payload,
)


def test_job_record_round_trips_dict() -> None:
    record = JobRecord(
        job_id="job-1",
        user_id="user-1",
        status="running",
        input_video_path="/tmp/in.mp4",
        output_root="/tmp/out",
        current_stage="narration",
        progress={"completedSegments": 2},
        artifacts={"workflowJsonPath": "/tmp/out/workflow.json"},
    )

    data = record.to_dict()
    parsed = job_record_from_dict(data)

    assert parsed == record
    assert data["created_at"].endswith("Z")
    assert data["updated_at"].endswith("Z")


def test_job_record_from_dict_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="unsupported job status"):
        job_record_from_dict(
            {
                "job_id": "job-1",
                "status": "unknown",
                "input_video_path": "/tmp/in.mp4",
                "output_root": "/tmp/out",
            }
        )


def test_job_record_from_dict_defaults_optional_fields() -> None:
    record = job_record_from_dict(
        {
            "job_id": "job-2",
            "status": "queued",
            "input_video_path": "/tmp/in.mp4",
            "output_root": "/tmp/out",
        }
    )

    assert record.user_id is None
    assert record.current_stage is None
    assert record.progress == {}
    assert record.error is None
    assert record.artifacts == {}


def test_job_record_file_round_trip(tmp_path) -> None:
    record = JobRecord(
        job_id="job-file",
        status="succeeded",
        input_video_path="/tmp/in.mp4",
        output_root="/tmp/out",
        artifacts={"videoPath": "/tmp/in.mp4"},
    )
    path = tmp_path / "workflow.json"

    written = write_job_record(record, path)
    parsed = read_job_record(written)

    assert parsed == record


def test_job_paths_resolve_standard_layout(tmp_path) -> None:
    paths = JobPaths.resolve(jobs_root=tmp_path / "jobs", job_id="job-1")

    assert paths.root == str((tmp_path / "jobs" / "job-1").resolve())
    assert paths.workflow_log_path.endswith("job-1/logs/workflow.jsonl")
    assert paths.workflow_json_path.endswith("job-1/workflow.json")
    assert paths.extracted_srt_path.endswith("job-1/subtitles/extracted.srt")
    assert paths.final_subtitled_srt_path.endswith("job-1/subtitles/final.subtitled.srt")
    assert paths.subtitle_analysis_json_path.endswith("job-1/analysis/subtitle_analysis.json")
    assert paths.frame_pool_manifest_path.endswith("job-1/frame_pool/manifest.jsonl")
    assert paths.narration_json_path.endswith("job-1/narration/narration.json")
    assert paths.speech_video_json_path.endswith("job-1/speech/speech_video.json")
    assert paths.rendered_video_path.endswith("job-1/render/narrated.mp4")
    assert paths.study_cards_html_path.endswith("job-1/study_cards/study_cards.html")


def test_job_paths_ensure_dirs_creates_standard_directories(tmp_path) -> None:
    paths = JobPaths.resolve(jobs_root=tmp_path / "jobs", job_id="job-2")

    paths.ensure_dirs()

    for directory in (
        paths.input_dir,
        paths.logs_dir,
        paths.subtitles_dir,
        paths.analysis_dir,
        paths.frame_pool_dir,
        paths.narration_dir,
        paths.speech_audio_dir,
        paths.render_dir,
        paths.study_cards_dir,
    ):
        assert Path(directory).is_dir()


def test_job_paths_reject_unsafe_job_id(tmp_path) -> None:
    with pytest.raises(ValueError, match="unsafe job_id"):
        JobPaths.resolve(jobs_root=tmp_path, job_id="../bad")


def test_job_store_writes_initial_running_record(tmp_path) -> None:
    store = JobStore.resolve(jobs_root=tmp_path / "jobs", job_id="job-running")
    store.ensure_dirs()

    record = store.write_initial(
        status="running",
        input_video_path="/tmp/demo.mp4",
        user_id="user-1",
        current_stage="workflow",
    )
    parsed = store.read()

    assert parsed == record
    assert parsed.job_id == "job-running"
    assert parsed.status == "running"
    assert parsed.input_video_path == "/tmp/demo.mp4"
    assert parsed.output_root == store.paths.root
    assert parsed.user_id == "user-1"
    assert parsed.current_stage == "workflow"
    assert parsed.created_at == parsed.updated_at


def test_workflow_artifacts_round_trip_payload_dict() -> None:
    artifacts = WorkflowArtifacts(
        video_path="demo.mp4",
        srt_path="demo.srt",
        frame_pool_manifest="frame_pool/manifest.jsonl",
        subtitle_context_index_dir="ctx",
        output_root="out",
        text_json_path="text.json",
        speech_json_path="speech.json",
        render_json_path="render.json",
        final_srt_path="final.srt",
        study_cards_html_path="cards.html",
        study_cards_html_error=None,
    )

    payload = artifacts.to_payload_dict()
    parsed = workflow_artifacts_from_payload(payload)

    assert parsed == artifacts
    assert payload == {
        "videoPath": "demo.mp4",
        "srtPath": "demo.srt",
        "framePoolManifest": "frame_pool/manifest.jsonl",
        "subtitleContextIndexDir": "ctx",
        "outputRoot": "out",
        "textJsonPath": "text.json",
        "speechJsonPath": "speech.json",
        "renderJsonPath": "render.json",
        "finalSrtPath": "final.srt",
        "studyCardsHtmlPath": "cards.html",
        "studyCardsHtmlError": None,
    }


def test_workflow_artifacts_from_payload_preserves_none_optional_paths() -> None:
    artifacts = workflow_artifacts_from_payload(
        {
            "videoPath": "demo.mp4",
            "srtPath": "demo.srt",
            "framePoolManifest": None,
            "subtitleContextIndexDir": None,
            "outputRoot": "out",
        }
    )

    assert artifacts.frame_pool_manifest is None
    assert artifacts.subtitle_context_index_dir is None
    assert artifacts.text_json_path is None
