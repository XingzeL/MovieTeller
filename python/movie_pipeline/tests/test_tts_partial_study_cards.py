from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from movieteller_config.schema import settings_from_dict
from movieteller_logging import events as log_events

from movie_pipeline import WorkflowRequest, resolved_run_context_from_request, run_full_workflow

_SINGLE_GAP_SRT = """1
00:00:01,250 --> 00:00:02,250
x
"""
_SINGLE_GAP_VIDEO_DUR = 2.3


def _settings(**overrides):
    base = {
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
        "logging": {
            "enabled": True,
            "level": "INFO",
            "format": "jsonl",
            "stderr": False,
        },
    }
    base.update(overrides)
    return settings_from_dict(base)


def test_tts_partial_failure_still_exports_study_cards(tmp_path: Path) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    srt = tmp_path / "demo.extracted.srt"
    srt.write_text(_SINGLE_GAP_SRT, encoding="utf-8")
    pool_dir = tmp_path / "demo.frame_pool"
    pool_dir.mkdir()
    (pool_dir / "manifest.jsonl").write_text("", encoding="utf-8")
    ctx_dir = tmp_path / "demo.subtitle_context"
    ctx_dir.mkdir()
    (ctx_dir / "chunks.jsonl").write_text("", encoding="utf-8")

    import numpy as np

    np.save(ctx_dir / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))

    request = WorkflowRequest(
        video_path=str(video),
        output_root=str(tmp_path),
        user_id="tts-partial-user",
        enable_polish=False,
        enable_speech=True,
        enable_embed_video=True,
    )
    resolved_context = resolved_run_context_from_request(
        request=request,
        settings=_settings(),
    )
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=replace(
                resolved_context.execution,
                pipeline=replace(
                    resolved_context.execution.pipeline,
                    video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                ),
            ),
        )
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        return ("narration", end_sec - start_sec)

    def failing_synthesizer(*_args, **_kwargs):
        raise RuntimeError("tts provider down")

    run_full_workflow(
        resolved_context=resolved_context,
        narrator=fake_narrator,
        synthesizer=failing_synthesizer,
    )

    workflow = json.loads((tmp_path / "workflow.json").read_text(encoding="utf-8"))
    assert workflow["status"] == "failed"
    assert workflow["error"]["error_code"] == "tts_partial_failure"
    assert workflow["error"]["retryable"] is True
    assert workflow["artifacts"].get("studyCardsHtmlPath")
    assert Path(workflow["artifacts"]["studyCardsHtmlPath"]).is_file()
    assert workflow["artifacts"].get("ttsPartialFailure", {}).get("failed", 0) >= 1

    log_path = tmp_path / "logs" / "workflow.jsonl"
    events = [json.loads(line)["event"] for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert log_events.SEGMENT_TTS_FAILED in events
    rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(
        row.get("event") == log_events.WORKFLOW_STAGE_DONE
        and row.get("stage") == "export"
        for row in rows
    )

    manifest = json.loads((tmp_path / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in manifest}
    assert "studyCardsHtml" in kinds
    assert "renderedVideo" not in kinds
