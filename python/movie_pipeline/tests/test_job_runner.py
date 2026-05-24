from __future__ import annotations

from pathlib import Path

import numpy as np

from movieteller_config.schema import settings_from_dict
from movie_pipeline import JobPaths, WorkflowRequest, build_job_request, read_job_record, run_workflow_job


_SINGLE_GAP_SRT = """1
00:00:01,250 --> 00:00:02,250
x
"""


def _settings():
    return settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "model_defaults": {
                "narration": "gpt-4o-mini",
                "polish": "gpt-4.1-mini",
                "tts": "qwen3-tts-flash",
                "embedding": "text-embedding-3-small",
            },
            "ffmpeg_path": "ffmpeg",
            "max_frames_per_segment": 4,
            "narration_frame_max_edge": 768,
            "pool_miss_uniform_max_frames": 2,
            "tts_defaults": {"voice": "en-US-EmmaMultilingualNeural"},
            "logging": {"enabled": True, "stderr": False},
        }
    )


def _seed_resume_artifacts(job_root: Path, video_stem: str) -> None:
    job_root.mkdir(parents=True, exist_ok=True)
    (job_root / f"{video_stem}.extracted.srt").write_text(_SINGLE_GAP_SRT, encoding="utf-8")
    pool_dir = job_root / f"{video_stem}.frame_pool"
    pool_dir.mkdir(parents=True)
    (pool_dir / "manifest.jsonl").write_text("", encoding="utf-8")
    ctx_dir = job_root / f"{video_stem}.subtitle_context"
    ctx_dir.mkdir()
    (ctx_dir / "chunks.jsonl").write_text("", encoding="utf-8")
    np.save(ctx_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))


def test_build_job_request_binds_job_identity(tmp_path) -> None:
    video = tmp_path / "input.mp4"
    request = WorkflowRequest(
        video_path="ignored.mp4",
        output_root="ignored-out",
        workspace_id="ignored-workspace",
        user_id="request-user",
        user_tier="pro",
        enable_speech=True,
    )

    bound = build_job_request(
        job_id="job-1",
        jobs_root=tmp_path / "jobs",
        video_path=video,
        request=request,
        user_id="override-user",
    )

    assert bound.video_path == str(video)
    assert bound.output_root == str((tmp_path / "jobs" / "job-1").resolve())
    assert bound.workspace_id == "job-1"
    assert bound.user_id == "override-user"
    assert bound.user_tier == "pro"
    assert bound.enable_speech is True


def test_run_workflow_job_uses_standard_job_root_and_manifest(tmp_path, monkeypatch) -> None:
    jobs_root = tmp_path / "jobs"
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    paths = JobPaths.resolve(jobs_root=jobs_root, job_id="job-run")
    _seed_resume_artifacts(Path(paths.root), video.stem)
    monkeypatch.setattr(
        "subtitle_analysis.analyze.probe_video_duration_sec",
        lambda *args, **kwargs: 2.3,
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    record = run_workflow_job(
        job_id="job-run",
        jobs_root=jobs_root,
        video_path=video,
        settings=_settings(),
        request=WorkflowRequest(
            video_path=str(video),
            enable_polish=False,
            enable_speech=False,
            enable_embed_video=False,
            enable_subtitle_context=True,
            min_gap_sec=1.0,
        ),
        user_id="user-1",
        narrator=fake_narrator,
    )

    assert record.job_id == "job-run"
    assert record.user_id == "user-1"
    assert record.status == "succeeded"
    assert record.output_root == paths.root
    assert Path(paths.workflow_json_path).is_file()
    assert Path(paths.workflow_log_path).is_file()
    assert record.artifacts["videoPath"] == str(video.resolve())
    assert record.artifacts["outputRoot"] == paths.root


def test_run_workflow_job_writes_running_record_before_workflow(tmp_path, monkeypatch) -> None:
    jobs_root = tmp_path / "jobs"
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    paths = JobPaths.resolve(jobs_root=jobs_root, job_id="job-running")
    _seed_resume_artifacts(Path(paths.root), video.stem)
    monkeypatch.setattr(
        "subtitle_analysis.analyze.probe_video_duration_sec",
        lambda *args, **kwargs: 2.3,
    )

    observed = {}

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        observed["record"] = read_job_record(paths.workflow_json_path)
        return ("narration", end_sec - start_sec)

    record = run_workflow_job(
        job_id="job-running",
        jobs_root=jobs_root,
        video_path=video,
        settings=_settings(),
        request=WorkflowRequest(
            video_path=str(video),
            enable_polish=False,
            enable_speech=False,
            enable_embed_video=False,
            enable_subtitle_context=True,
            min_gap_sec=1.0,
        ),
        user_id="user-1",
        narrator=fake_narrator,
    )

    running = observed["record"]
    assert running.status == "running"
    assert running.job_id == "job-running"
    assert running.current_stage == "workflow"
    assert running.user_id == "user-1"
    assert record.status == "succeeded"
