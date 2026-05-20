from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from movieteller_config.schema import (
    FramePoolBuildOptions,
    NarrationOptions,
    NarrationPolishOptions,
    NarrationSpeechOptions,
    NarrationVideoOptions,
    SubtitleExtractionOptions,
    SubtitleContextBuildOptions,
    SubtitleContextRetrieveOptions,
)

if TYPE_CHECKING:
    from frame_source import FrameSourceOptions


@dataclass(frozen=True)
class NarrationPolishDetails:
    text: str
    segment_duration_sec: float
    target_duration_sec: float
    safety_margin_sec: float
    speaking_rate_wpm: int
    target_word_count: int
    original_word_count: int
    polished_word_count: int
    estimated_original_duration_sec: float
    estimated_polished_duration_sec: float
    cefr_level: str
    strength: str
    provider: str
    model: str
    timing_api_sec: float | None = None

    @property
    def fits_duration(self) -> bool:
        return self.estimated_polished_duration_sec <= self.target_duration_sec


@dataclass(frozen=True)
class NarrationSpeechDetails:
    text: str
    audio_path: str
    metadata_path: str | None
    segment_duration_sec: float
    target_duration_sec: float
    raw_duration_sec: float
    audio_duration_sec: float
    provider: str
    voice: str
    rate: str
    volume: str
    pitch: str
    boundary: str
    fit_applied: bool
    timing_tts_sec: float | None = None
    timing_fit_sec: float | None = None

    @property
    def duration_delta_sec(self) -> float:
        return self.audio_duration_sec - self.target_duration_sec

    @property
    def fits_duration(self) -> bool:
        return self.audio_duration_sec <= (self.target_duration_sec + 0.05)


@dataclass(frozen=True)
class NarratedSegment:
    start_sec: float
    end_sec: float
    narration_text: str
    prev_subtitle_text: str | None
    next_subtitle_text: str | None
    speech_text: str | None = None
    polish: NarrationPolishDetails | None = None
    speech: NarrationSpeechDetails | None = None
    timing_extract_sec: float | None = None
    timing_api_sec: float | None = None
    timing_total_sec: float | None = None
    frame_count: int | None = None

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

    @property
    def final_text(self) -> str:
        return self.speech_text or self.narration_text


@dataclass(frozen=True)
class MoviePipelineOptions:
    video_duration_sec: float | None = None
    min_gap_sec: float = 1.0
    subtitle_guard_sec: float = 0.25
    ffprobe_bin: str = "ffprobe"
    subtitle_context_index_dir: str | None = None
    build_subtitle_context: bool = False
    speech_output_dir: str | None = None
    embed_video: bool = False
    embed_output_path: str | None = None
    narration_options: NarrationOptions | None = None
    frame_source_options: FrameSourceOptions | None = None
    subtitle_context_build_options: SubtitleContextBuildOptions | None = None
    subtitle_context_retrieve_options: SubtitleContextRetrieveOptions | None = None
    polish_options: NarrationPolishOptions | None = None
    speech_options: NarrationSpeechOptions | None = None
    video_options: NarrationVideoOptions | None = None


PipelineRuntimeOptions: TypeAlias = MoviePipelineOptions
"""Alias for staged naming; same shape as :class:`MoviePipelineOptions`."""


@dataclass(frozen=True)
class FullWorkflowPlan:
    """Which workflow stages are enabled (see :class:`FullWorkflowOptions`)."""

    extract_subtitles: bool = True
    build_frame_pool: bool = True
    build_subtitle_context: bool = True
    enable_polish: bool = True
    enable_speech: bool = False
    enable_embed_video: bool = False


@dataclass(frozen=True)
class ArtifactPaths:
    """Fixed on-disk layout under ``output_root`` for ``run_full_workflow``."""

    output_root: str
    source_video: str
    stem: str
    srt_path: str
    frame_pool_dir: str
    frame_pool_manifest: str
    subtitle_context_dir: str
    speech_output_dir: str | None
    embed_output_path: str | None

    @staticmethod
    def resolve(
        *,
        output_root: str | Path,
        source_video: str | Path,
        enable_speech: bool,
        enable_embed_video: bool,
    ) -> ArtifactPaths:
        root = Path(output_root).resolve()
        vid = Path(source_video).resolve()
        stem = vid.stem
        speech = str(root / f"{stem}.narration_audio") if enable_speech else None
        embed = str(root / f"{stem}.narrated.mp4") if enable_embed_video else None
        pool_dir = root / f"{stem}.frame_pool"
        return ArtifactPaths(
            output_root=str(root),
            source_video=str(vid),
            stem=stem,
            srt_path=str(root / f"{stem}.extracted.srt"),
            frame_pool_dir=str(pool_dir),
            frame_pool_manifest=str(pool_dir / "manifest.jsonl"),
            subtitle_context_dir=str(root / f"{stem}.subtitle_context"),
            speech_output_dir=speech,
            embed_output_path=embed,
        )


@dataclass(frozen=True)
class FullWorkflowOptions:
    extract_subtitles: bool = True
    build_frame_pool: bool = True
    build_subtitle_context: bool = True
    enable_polish: bool = True
    enable_speech: bool = False
    enable_embed_video: bool = False
    output_root: str | None = None
    subtitle_extraction_options: SubtitleExtractionOptions | None = None
    frame_pool_build_options: FramePoolBuildOptions | None = None
    subtitle_context_build_options: SubtitleContextBuildOptions | None = None
    movie_pipeline_options: MoviePipelineOptions | None = None

    def workflow_plan(self) -> FullWorkflowPlan:
        return FullWorkflowPlan(
            extract_subtitles=self.extract_subtitles,
            build_frame_pool=self.build_frame_pool,
            build_subtitle_context=self.build_subtitle_context,
            enable_polish=self.enable_polish,
            enable_speech=self.enable_speech,
            enable_embed_video=self.enable_embed_video,
        )
