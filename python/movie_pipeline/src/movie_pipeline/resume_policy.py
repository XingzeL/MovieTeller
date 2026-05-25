"""Explicit run vs skip decisions for workflow stages (resume-by-artifact).

Stages used to interleave ``check_*`` booleans with logging status strings; this
module names those decisions in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from movie_pipeline.workflow_artifacts import ArtifactCheck

StageLogStatus = Literal["run", "skipped"]


@dataclass(frozen=True)
class SubtitleExtractionPolicy:
    """Whether subtitle extraction runs, skips, or must error."""

    log_status: StageLogStatus
    run_extract: bool
    artifact_missing: bool

    @staticmethod
    def resolve(
        *,
        extract_subtitles: bool,
        force_rebuild_subtitles: bool,
        check: ArtifactCheck,
    ) -> "SubtitleExtractionPolicy":
        needs_extract = force_rebuild_subtitles or not check.reusable
        run_extract = extract_subtitles and needs_extract
        log_status: StageLogStatus = "run" if run_extract else "skipped"
        return SubtitleExtractionPolicy(
            log_status=log_status,
            run_extract=run_extract,
            artifact_missing=not check.reusable,
        )


@dataclass(frozen=True)
class FramePoolPolicy:
    log_status: StageLogStatus
    run_build: bool

    @staticmethod
    def resolve(
        *,
        build_frame_pool: bool,
        force_rebuild_frame_pool: bool,
        check: ArtifactCheck,
    ) -> "FramePoolPolicy":
        needs_rebuild = force_rebuild_frame_pool or not check.reusable
        run_build = build_frame_pool and needs_rebuild
        log_status: StageLogStatus = "run" if run_build else "skipped"
        return FramePoolPolicy(log_status=log_status, run_build=run_build)


@dataclass(frozen=True)
class SubtitleContextPolicy:
    """Only used when ``build_subtitle_context`` is already known to be true."""

    log_status: StageLogStatus
    run_build: bool

    @staticmethod
    def resolve(
        *,
        force_rebuild_subtitle_context: bool,
        check: ArtifactCheck,
    ) -> "SubtitleContextPolicy":
        needs_rebuild = force_rebuild_subtitle_context or not check.reusable
        log_status: StageLogStatus = "run" if needs_rebuild else "skipped"
        return SubtitleContextPolicy(log_status=log_status, run_build=needs_rebuild)


@dataclass(frozen=True)
class VideoPackagePolicy:
    log_status: StageLogStatus
    run_render: bool

    @staticmethod
    def resolve(*, enable_embed_video: bool) -> "VideoPackagePolicy":
        if not enable_embed_video:
            return VideoPackagePolicy(log_status="skipped", run_render=False)
        return VideoPackagePolicy(log_status="run", run_render=True)
