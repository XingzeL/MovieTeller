from __future__ import annotations

from dataclasses import dataclass

from pipeline_types import SubtitleCue


@dataclass(frozen=True)
class ExtractionResult:
    subtitle_path: str
    cues: tuple[SubtitleCue, ...]
