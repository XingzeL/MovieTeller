from __future__ import annotations

from pathlib import Path

from movie_pipeline.artifact_manifest import (
    build_product_artifact_manifest,
    write_product_artifact_manifest,
    workflow_artifacts_payload_from_entries,
)
from movie_pipeline.job import JobPaths
from movie_pipeline.types import ArtifactPaths


def test_build_manifest_uses_rendered_video_mp4(tmp_path: Path) -> None:
    output_root = tmp_path / "job-1"
    output_root.mkdir()
    video = output_root / "input" / "source.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"vid")
    srt = output_root / "subtitles" / "extracted.srt"
    srt.parent.mkdir(parents=True)
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    rendered = output_root / "render" / "narrated.mp4"
    rendered.parent.mkdir(parents=True)
    rendered.write_bytes(b"mp4")

    job_paths = JobPaths.resolve(jobs_root=tmp_path, job_id="job-1")
    paths = ArtifactPaths.resolve_for_job_paths(
        job_paths=job_paths,
        source_video=video,
        enable_speech=False,
        enable_embed_video=True,
    )
    payload = {
        "renderedVideo": {"outputPath": str(rendered)},
        "workflowArtifacts": {},
    }
    entries = build_product_artifact_manifest(
        paths=paths,
        payload=payload,
        job_paths=job_paths,
        output_root=output_root,
    )
    kinds = {entry["kind"] for entry in entries}
    assert kinds <= {"renderedVideo", "studyCardsHtml"}
    assert "sourceVideo" not in kinds
    assert "extractedSrt" not in kinds
    assert "renderedVideo" in kinds
    rendered_entry = next(e for e in entries if e["kind"] == "renderedVideo")
    assert rendered_entry["path"].endswith("narrated.mp4")
    assert Path(rendered_entry["path"]).is_file()

    manifest_path = write_product_artifact_manifest(
        output_root=output_root,
        entries=entries,
    )
    assert Path(manifest_path).is_file()
    merged = workflow_artifacts_payload_from_entries(
        entries,
        base={"outputRoot": str(output_root)},
    )
    assert merged["renderedVideoPath"] == str(rendered.resolve())
