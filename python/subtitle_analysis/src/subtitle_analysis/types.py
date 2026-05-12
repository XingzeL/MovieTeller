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
class SubtitleAnalysisResult:
    video_duration_sec: float | None
    subtitle_spans: tuple[TimeSpan, ...]
    raw_gaps: tuple[TimeSpan, ...]
    narration_candidates: tuple[NarrationCandidate, ...]
