from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from movie_pipeline.job import JobPaths
from movie_pipeline.types import ArtifactPaths


def _file_entry(
    *,
    kind: str,
    label: str,
    path: str | Path | None,
    media_type: str | None = None,
) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = Path(path).resolve()
    if not resolved.is_file():
        return None
    entry: dict[str, Any] = {
        "kind": kind,
        "label": label,
        "path": str(resolved),
    }
    if media_type:
        entry["mediaType"] = media_type
    return entry


def build_product_artifact_manifest(
    *,
    paths: ArtifactPaths,
    payload: dict[str, Any],
    job_paths: JobPaths | None,
    output_root: Path,
) -> list[dict[str, Any]]:
    """Collect user-facing downloadable artifacts for ``artifacts/manifest.json``.

    Product surface is limited to narrated video and study cards; intermediate
    files (SRT, JSON manifests, etc.) stay on disk but are not listed.
    """
    entries: list[dict[str, Any]] = []
    workflow_artifacts = dict(payload.get("workflowArtifacts") or {})

    def add(entry: dict[str, Any] | None) -> None:
        if entry is not None:
            entries.append(entry)

    rendered_video = None
    rendered_payload = payload.get("renderedVideo")
    if isinstance(rendered_payload, dict):
        rendered_video = rendered_payload.get("outputPath")
    if not rendered_video:
        rendered_video = paths.embed_output_path
    if job_paths is not None and rendered_video:
        if not Path(rendered_video).is_file() and Path(job_paths.rendered_video_path).is_file():
            rendered_video = job_paths.rendered_video_path
    elif job_paths is not None:
        rendered_video = job_paths.rendered_video_path
    add(
        _file_entry(
            kind="renderedVideo",
            label="旁白成片",
            path=rendered_video,
            media_type="video/mp4",
        )
    )

    study_html = workflow_artifacts.get("studyCardsHtmlPath") or paths.study_cards_html_path
    add(
        _file_entry(
            kind="studyCardsHtml",
            label="学习卡片",
            path=study_html,
            media_type="text/html",
        )
    )

    return entries


def write_product_artifact_manifest(
    *,
    output_root: Path,
    entries: list[dict[str, Any]],
) -> str:
    manifest_dir = output_root / "artifacts"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(manifest_path.resolve())


def workflow_artifacts_payload_from_entries(
    entries: list[dict[str, Any]],
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Merge manifest paths into camelCase workflowArtifacts for workflow.json."""
    out = dict(base)
    kind_to_key = {
        "sourceVideo": "videoPath",
        "extractedSrt": "srtPath",
        "finalSrt": "finalSrtPath",
        "narrationJson": "textJsonPath",
        "speechJson": "speechJsonPath",
        "renderedVideo": "renderedVideoPath",
        "studyCardsHtml": "studyCardsHtmlPath",
        "framePoolManifest": "framePoolManifest",
    }
    for entry in entries:
        kind = str(entry.get("kind") or "")
        key = kind_to_key.get(kind)
        path = entry.get("path")
        if key and path:
            out[key] = str(path)
    output_root = base.get("outputRoot")
    if output_root:
        out["artifactManifestPath"] = str(
            (Path(str(output_root)) / "artifacts" / "manifest.json").resolve()
        )
    return out
