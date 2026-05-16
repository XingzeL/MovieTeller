from __future__ import annotations

from dataclasses import dataclass

from pipeline_types import NarrationAudioSegment


@dataclass(frozen=True)
class NarrationVideoRenderResult:
    video_path: str
    output_path: str
    segment_count: int
    video_duration_sec: float
    background_audio_volume: float
    speech_audio_volume: float
    subtitle_srt_path: str | None = None
    timing_render_sec: float | None = None
