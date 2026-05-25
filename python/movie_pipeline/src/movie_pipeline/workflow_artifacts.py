from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from subtitle_context.index import subtitle_context_index_is_complete

from movie_pipeline.types import ArtifactPaths


@dataclass(frozen=True)
class ArtifactCheck:
    exists: bool
    path: str
    reason: str | None = None

    @property
    def reusable(self) -> bool:
        return self.exists and self.reason is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "reusable": self.reusable,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StageArtifactManifest:
    source_video: str
    output_root: str
    stages: dict[str, dict[str, dict[str, Any]]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceVideo": self.source_video,
            "outputRoot": self.output_root,
            "stages": self.stages,
        }


def check_subtitle_srt(path: str | Path) -> ArtifactCheck:
    target = Path(path)
    if not target.is_file():
        return ArtifactCheck(False, str(target), "missing")
    if target.stat().st_size <= 0:
        return ArtifactCheck(True, str(target), "empty")
    return ArtifactCheck(True, str(target))


def check_frame_pool_manifest(path: str | Path) -> ArtifactCheck:
    target = Path(path)
    if not target.is_file():
        return ArtifactCheck(False, str(target), "missing")
    return ArtifactCheck(True, str(target))


def check_subtitle_context_index(path: str | Path) -> ArtifactCheck:
    target = Path(path)
    if subtitle_context_index_is_complete(target):
        return ArtifactCheck(True, str(target))
    return ArtifactCheck(target.exists(), str(target), "incomplete")


def build_stage_artifact_manifest(paths: ArtifactPaths) -> StageArtifactManifest:
    return StageArtifactManifest(
        source_video=paths.source_video,
        output_root=paths.output_root,
        stages={
            "subtitle_extraction": {
                "outputs": {
                    "srt": check_subtitle_srt(paths.srt_path).to_dict(),
                },
            },
            "frame_pool": {
                "inputs": {
                    "srt": check_subtitle_srt(paths.srt_path).to_dict(),
                },
                "outputs": {
                    "manifest": check_frame_pool_manifest(paths.frame_pool_manifest).to_dict(),
                },
            },
            "subtitle_context": {
                "inputs": {
                    "srt": check_subtitle_srt(paths.srt_path).to_dict(),
                },
                "outputs": {
                    "index": check_subtitle_context_index(paths.subtitle_context_dir).to_dict(),
                },
            },
        },
    )


def write_stage_artifact_manifest(
    *,
    paths: ArtifactPaths,
    output_path: str | Path | None = None,
) -> str:
    target = Path(output_path) if output_path is not None else _default_manifest_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_stage_artifact_manifest(paths)
    target.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(target)


def _default_manifest_path(paths: ArtifactPaths) -> Path:
    return Path(paths.output_root) / f"{paths.stem}.artifact_manifest.json"
