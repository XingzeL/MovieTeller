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
    """Collect downloadable artifacts for ``artifacts/manifest.json``."""
    entries: list[dict[str, Any]] = []
    workflow_artifacts = dict(payload.get("workflowArtifacts") or {})

    def add(entry: dict[str, Any] | None) -> None:
        if entry is not None:
            entries.append(entry)

    add(
        _file_entry(
            kind="sourceVideo",
            label="Source video",
            path=paths.source_video,
            media_type="video/mp4",
        )
    )
    add(
        _file_entry(
            kind="extractedSrt",
            label="Extracted subtitles",
            path=paths.srt_path,
            media_type="application/x-subrip",
        )
    )

    final_srt = workflow_artifacts.get("finalSrtPath")
    if job_paths is not None and not final_srt:
        final_srt = job_paths.final_subtitled_srt_path
    add(
        _file_entry(
            kind="finalSrt",
            label="Final subtitles",
            path=final_srt,
            media_type="application/x-subrip",
        )
    )

    narration_json = None
    if job_paths is not None:
        narration_json = job_paths.narration_json_path
    stem = paths.stem
    if narration_json is None:
        candidate = output_root / f"{stem}.narration.json"
        if candidate.is_file():
            narration_json = str(candidate)
    add(
        _file_entry(
            kind="narrationJson",
            label="Narration JSON",
            path=narration_json,
            media_type="application/json",
        )
    )

    speech_json = workflow_artifacts.get("speechJsonPath")
    if job_paths is not None and not speech_json:
        speech_json = job_paths.speech_video_json_path
    if speech_json is None:
        candidate = output_root / f"{stem}.speech.json"
        if candidate.is_file():
            speech_json = str(candidate)
    add(
        _file_entry(
            kind="speechJson",
            label="Speech manifest",
            path=speech_json,
            media_type="application/json",
        )
    )

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
            label="Rendered video",
            path=rendered_video,
            media_type="video/mp4",
        )
    )

    study_html = workflow_artifacts.get("studyCardsHtmlPath") or paths.study_cards_html_path
    add(
        _file_entry(
            kind="studyCardsHtml",
            label="Study cards",
            path=study_html,
            media_type="text/html",
        )
    )

    frame_pool = workflow_artifacts.get("framePoolManifest") or paths.frame_pool_manifest
    add(
        _file_entry(
            kind="framePoolManifest",
            label="Frame pool manifest",
            path=frame_pool,
            media_type="application/jsonl",
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
