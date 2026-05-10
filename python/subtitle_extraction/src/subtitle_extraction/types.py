from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    """One subtitle line with seconds-based timeline."""

    start_sec: float
    end_sec: float
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    subtitle_path: str
    cues: tuple[SubtitleCue, ...]
