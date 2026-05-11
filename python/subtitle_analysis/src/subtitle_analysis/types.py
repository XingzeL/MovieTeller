from __future__ import annotations

from dataclasses import dataclass

from pipeline_types import NarrationCandidate


@dataclass(frozen=True)
class TimeSpan:
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

@dataclass(frozen=True)
class NarratedSegment:
    start_sec: float
    end_sec: float
    narration_text: str
    prev_subtitle_text: str | None
    next_subtitle_text: str | None
    speech_text: str | None = None
    polish: "NarrationPolishDetails | None" = None
    speech: "NarrationSpeechDetails | None" = None
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
class SubtitleAnalysisResult:
    video_duration_sec: float | None
    subtitle_spans: tuple[TimeSpan, ...]
    raw_gaps: tuple[TimeSpan, ...]
    narration_candidates: tuple[NarrationCandidate, ...]
