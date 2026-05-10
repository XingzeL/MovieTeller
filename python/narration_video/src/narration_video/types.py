from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationAudioSegment:
    start_sec: float
    end_sec: float
    audio_path: str

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class NarrationVideoRenderResult:
    video_path: str
    output_path: str
    segment_count: int
    video_duration_sec: float
    background_audio_volume: float
    speech_audio_volume: float
    timing_render_sec: float | None = None
