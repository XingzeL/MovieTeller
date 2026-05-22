from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True)
class NarrationPolishResult:
    original_text: str
    polished_text: str
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
