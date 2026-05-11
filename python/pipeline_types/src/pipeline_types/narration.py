from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NarrationCandidate:
    start_sec: float
    end_sec: float
    prev_subtitle_text: str | None
    next_subtitle_text: str | None

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class FrameBatch:
    frames_base64_png: tuple[str, ...]
    frame_times_sec: tuple[float, ...]
    duration_sec: float
    source: Literal["uniform", "frame_pool", "external"]
    shot_ids: tuple[int | None, ...] | None = None


@dataclass(frozen=True)
class NarrationContext:
    segment_start_sec: float
    segment_end_sec: float
    prev_subtitle_text: str | None = None
    next_subtitle_text: str | None = None
    retrieved_context_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrationResult:
    text: str
    duration_sec: float
    frame_count: int
    frame_source: str
    timing_extract_sec: float | None = None
    timing_api_sec: float | None = None
    timing_total_sec: float | None = None


@dataclass(frozen=True)
class NarrationAudioSegment:
    start_sec: float
    end_sec: float
    audio_path: str

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec
