from __future__ import annotations

from pathlib import Path
import json

import numpy as np

from movie_pipeline.types import ArtifactPaths
from movie_pipeline.workflow_artifacts import (
    build_stage_artifact_manifest,
    check_frame_pool_manifest,
    check_subtitle_context_index,
    check_subtitle_srt,
    write_stage_artifact_manifest,
)


def test_check_subtitle_srt_requires_non_empty_file(tmp_path) -> None:
    missing = check_subtitle_srt(tmp_path / "missing.srt")
    assert missing.reusable is False
    assert missing.reason == "missing"

    empty_path = tmp_path / "empty.srt"
    empty_path.write_text("", encoding="utf-8")
    empty = check_subtitle_srt(empty_path)
    assert empty.exists is True
    assert empty.reusable is False
    assert empty.reason == "empty"

    ready_path = tmp_path / "ready.srt"
    ready_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    ready = check_subtitle_srt(ready_path)
    assert ready.reusable is True
    assert ready.reason is None


def test_check_frame_pool_manifest_requires_file(tmp_path) -> None:
    missing = check_frame_pool_manifest(tmp_path / "manifest.jsonl")
    assert missing.reusable is False
    assert missing.reason == "missing"

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    ready = check_frame_pool_manifest(manifest)
    assert ready.reusable is True


def test_check_subtitle_context_index_requires_complete_index(tmp_path) -> None:
    missing = check_subtitle_context_index(tmp_path / "ctx")
    assert missing.exists is False
    assert missing.reusable is False
    assert missing.reason == "incomplete"

    incomplete = tmp_path / "ctx"
    incomplete.mkdir()
    (incomplete / "chunks.jsonl").write_text("", encoding="utf-8")
    assert check_subtitle_context_index(incomplete).reason == "incomplete"

    np.save(incomplete / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))
    ready = check_subtitle_context_index(incomplete)
    assert ready.reusable is True
    assert ready.reason is None


def test_stage_artifact_manifest_records_reusable_outputs(tmp_path) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    paths = ArtifactPaths.resolve(
        output_root=tmp_path,
        source_video=video,
        enable_speech=False,
        enable_embed_video=False,
    )
    Path(paths.srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    frame_pool = Path(paths.frame_pool_dir)
    frame_pool.mkdir()
    Path(paths.frame_pool_manifest).write_text("", encoding="utf-8")
    ctx = Path(paths.subtitle_context_dir)
    ctx.mkdir()
    (ctx / "chunks.jsonl").write_text("", encoding="utf-8")
    np.save(ctx / "embeddings.npy", np.zeros((0, 0), dtype=np.float32))

    manifest = build_stage_artifact_manifest(paths).to_dict()

    assert manifest["sourceVideo"] == str(video.resolve())
    assert manifest["stages"]["subtitle_extraction"]["outputs"]["srt"]["reusable"] is True
    assert manifest["stages"]["frame_pool"]["outputs"]["manifest"]["reusable"] is True
    assert manifest["stages"]["subtitle_context"]["outputs"]["index"]["reusable"] is True


def test_write_stage_artifact_manifest_writes_default_file(tmp_path) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"fake")
    paths = ArtifactPaths.resolve(
        output_root=tmp_path,
        source_video=video,
        enable_speech=False,
        enable_embed_video=False,
    )

    out = write_stage_artifact_manifest(paths=paths)

    assert Path(out).name == "demo.artifact_manifest.json"
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data["stages"]["subtitle_extraction"]["outputs"]["srt"]["reason"] == "missing"
