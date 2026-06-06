from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, TypeAlias

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
    scene_title_zh: str | None = None

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
    vocab_study_card: dict[str, Any] | None = None
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
class NarrationPipelineConfig:
    video_duration_sec: float | None = None
    min_gap_sec: float = 1.0
    subtitle_guard_sec: float = 0.25
    ffprobe_bin: str = "ffprobe"
    narration_options: NarrationOptions | None = None
    frame_source_options: FrameSourceOptions | None = None
    subtitle_context_build_options: SubtitleContextBuildOptions | None = None
    subtitle_context_retrieve_options: SubtitleContextRetrieveOptions | None = None
    polish_options: NarrationPolishOptions | None = None
    speech_options: NarrationSpeechOptions | None = None
    video_options: NarrationVideoOptions | None = None

PipelineRuntimeConfig: TypeAlias = NarrationPipelineConfig
"""Alias for staged naming; same shape as :class:`NarrationPipelineConfig`."""


@dataclass(frozen=True)
class StudyCardSegment:
    start_sec: float
    end_sec: float
    narration_text: str
    prev_subtitle_text: str | None
    next_subtitle_text: str | None
    scene_title_zh: str | None = None
    vocab_study_card: dict[str, Any] | None = None


@dataclass(frozen=True)
class StudyCardsDocument:
    title: str
    segments: tuple[StudyCardSegment, ...]


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
    study_cards_html_path: str | None = None
    layout: str = "stem"

    @staticmethod
    def resolve(
        *,
        output_root: str | Path,
        source_video: str | Path,
        enable_speech: bool,
        enable_embed_video: bool,
        job_paths: Any | None = None,
    ) -> ArtifactPaths:
        if job_paths is not None:
            return ArtifactPaths.resolve_for_job_paths(
                job_paths=job_paths,
                source_video=source_video,
                enable_speech=enable_speech,
                enable_embed_video=enable_embed_video,
            )
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
            study_cards_html_path=str(root / f"{stem}.study_cards.html"),
            layout="stem",
        )

    @staticmethod
    def resolve_for_job_paths(
        *,
        job_paths: Any,
        source_video: str | Path,
        enable_speech: bool,
        enable_embed_video: bool,
    ) -> ArtifactPaths:
        vid = Path(source_video).resolve()
        speech = job_paths.speech_audio_dir if enable_speech else None
        embed = job_paths.rendered_video_path if enable_embed_video else None
        return ArtifactPaths(
            output_root=str(job_paths.root),
            source_video=str(vid),
            stem=vid.stem,
            srt_path=str(job_paths.extracted_srt_path),
            frame_pool_dir=str(job_paths.frame_pool_dir),
            frame_pool_manifest=str(job_paths.frame_pool_manifest_path),
            subtitle_context_dir=str(
                Path(job_paths.analysis_dir) / "subtitle_context"
            ),
            speech_output_dir=speech,
            embed_output_path=embed,
            study_cards_html_path=str(job_paths.study_cards_html_path),
            layout="job",
        )


@dataclass(frozen=True)
class ResolvedExecutionConfig:
    pipeline: NarrationPipelineConfig
    extract_subtitles: bool = True
    build_frame_pool: bool = True
    build_subtitle_context: bool = True
    force_rebuild_subtitles: bool = False
    force_rebuild_frame_pool: bool = False
    force_rebuild_subtitle_context: bool = False
    enable_polish: bool = True
    enable_speech: bool = False
    enable_embed_video: bool = False
    output_root: str | None = None
    subtitle_extraction_options: SubtitleExtractionOptions | None = None
    frame_pool_build_options: FramePoolBuildOptions | None = None
    subtitle_context_build_options: SubtitleContextBuildOptions | None = None


@dataclass(frozen=True)
class WorkflowRequest:
    """Frontend/API-facing workflow request: user intent and business inputs only."""

    video_path: str
    output_root: str | None = None
    prompt_style: str | None = None
    cefr_level: str | None = None
    min_gap_sec: float | None = None
    subtitle_guard_sec: float | None = None
    enable_subtitle_context: bool | None = None
    enable_polish: bool | None = None
    enable_speech: bool | None = None
    enable_embed_video: bool | None = None
    force_rebuild_subtitles: bool | None = None
    force_rebuild_frame_pool: bool | None = None
    force_rebuild_subtitle_context: bool | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    user_tier: str | None = None
    plan_code: str | None = None
    request_priority: str | None = None
    cost_mode: str | None = None
    max_cost_usd: float | None = None
    max_latency_sec: float | None = None
    tts_voice: str | None = None
    tts_language: str | None = None
    source_language: str | None = None
    narration_language: str | None = None
    subtitle_language: str | None = None
    start_point: float | None = None
    end_point: float | None = None


@dataclass(frozen=True)
class PolicyContext:
    """Server-side policy derived from user/account context."""

    resolved_level: str | None = None
    allow_subtitle_context: bool = True
    allow_polish: bool = True
    allow_speech: bool = True
    allow_embed_video: bool = True
    default_enable_subtitle_context: bool | None = None
    default_enable_polish: bool | None = None
    default_enable_speech: bool | None = None
    default_enable_embed_video: bool | None = None
    default_provider_override: str | None = None
    tts_provider_override: str | None = None
    api_provider_overrides: Mapping[str, str] | None = None
    api_key_overrides: Mapping[str, str] | None = None
    capability_model_overrides: Mapping[str, str] | None = None


@dataclass(frozen=True)
class ResolvedWorkflowConfig:
    """Resolved full-workflow configuration after settings + request + policy merge."""

    settings: object
    request: WorkflowRequest
    policy: PolicyContext
    execution: ResolvedExecutionConfig


@dataclass(frozen=True)
class ResolvedRunContext:
    """Preferred full-workflow entry payload for execution."""

    config: ResolvedWorkflowConfig

    @property
    def settings(self):
        return self.config.settings

    @property
    def execution(self) -> ResolvedExecutionConfig:
        return self.config.execution

    @property
    def request(self) -> WorkflowRequest:
        return self.config.request

    @property
    def policy(self) -> PolicyContext:
        return self.config.policy

    @property
    def video_path(self) -> str:
        return self.config.request.video_path
