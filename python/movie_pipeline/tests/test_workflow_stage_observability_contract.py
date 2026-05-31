from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from frame_source import FrameSourceOptions
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
    }
    base.update(overrides)
    return settings_from_dict(base)


def _frame_source_options(settings):
    return FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )


def test_full_workflow_emits_standard_stage_lifecycle_contract(tmp_path: Path) -> None:
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

    settings = _settings(
        logging={
            "enabled": True,
            "level": "INFO",
            "format": "jsonl",
            "stderr": False,
        }
    )
    request = WorkflowRequest(
        video_path=str(video),
        output_root=str(tmp_path),
        user_id="observability-user",
        enable_polish=False,
        enable_speech=False,
        enable_embed_video=False,
    )
    resolved_context = resolved_run_context_from_request(
        request=request,
        settings=settings,
    )
    resolved_context = type(resolved_context)(
        config=replace(
            resolved_context.config,
            execution=replace(
                resolved_context.execution,
                pipeline=replace(
                    resolved_context.execution.pipeline,
                    video_duration_sec=_SINGLE_GAP_VIDEO_DUR,
                    frame_source_options=_frame_source_options(settings),
                ),
            ),
        )
    )

    def fake_narrator(video_path, start_sec, end_sec, **kwargs):
        timings = kwargs.get("timings_out")
        if isinstance(timings, dict):
            timings["extract_sec"] = 0.01
            timings["api_sec"] = 0.01
            timings["total_sec"] = 0.02
            timings["frame_count"] = 1
        return ("narration", end_sec - start_sec)

    run_full_workflow(resolved_context=resolved_context, narrator=fake_narrator)

    _LEGACY_MACRO_EVENTS = frozenset(
        {
            "subtitle_extraction.start",
            "subtitle_extraction.done",
            "subtitle_extraction.failed",
            "frame_pool.start",
            "frame_pool.done",
            "frame_pool.failed",
            "subtitle_context.start",
            "subtitle_context.done",
            "subtitle_context.failed",
            "video_package.start",
            "video_package.done",
            "video_package.failed",
            "workflow_export.start",
            "workflow_export.done",
            "workflow_export.failed",
        }
    )

    log_path = tmp_path / "logs" / "workflow.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    legacy_hits = [row["event"] for row in rows if row.get("event") in _LEGACY_MACRO_EVENTS]
    assert legacy_hits == []
    stage_rows = [row for row in rows if str(row.get("event", "")).startswith("workflow.stage.")]
    by_stage: dict[str, list[dict]] = {}
    for row in stage_rows:
        by_stage.setdefault(str(row.get("stage")), []).append(row)

    for stage in log_events.FIXED_WORKFLOW_STAGES:
        assert stage in by_stage, stage
        stage_events = by_stage[stage]
        disabled_skip_only = not any(
            row["event"] == log_events.WORKFLOW_STAGE_START for row in stage_events
        ) and any(
            row["event"] == log_events.WORKFLOW_STAGE_SKIPPED
            and row.get("skip_reason") == "disabled_by_request"
            for row in stage_events
        )
        if not disabled_skip_only:
            assert any(
                row["event"] == log_events.WORKFLOW_STAGE_START for row in stage_events
            ), stage
        terminal = [
            row for row in by_stage[stage]
            if row["event"] in {
                log_events.WORKFLOW_STAGE_DONE,
                log_events.WORKFLOW_STAGE_SKIPPED,
                log_events.WORKFLOW_STAGE_FAILED,
            }
        ]
        assert terminal, stage
        for row in terminal:
            assert "duration_ms" in row, row
            if row["event"] == log_events.WORKFLOW_STAGE_SKIPPED:
                assert row.get("skip_reason"), row
            if row["event"] == log_events.WORKFLOW_STAGE_FAILED:
                assert row.get("error_code"), row
                assert row.get("error_message"), row
                assert "fatal" in row, row
