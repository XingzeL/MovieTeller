from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationSpeechResult:
    text: str
    segment_duration_sec: float
    target_duration_sec: float
    audio_path: str
    metadata_path: str | None
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
