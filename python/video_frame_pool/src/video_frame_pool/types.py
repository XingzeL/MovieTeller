from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShotSpan:
    shot_id: int
    start_sec: float
    end_sec: float
    is_dialogue: bool = False
    dialogue_overlap_ratio: float = 0.0
    non_dialogue_ranges: tuple[tuple[float, float], ...] = ()

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True)
class FramePoolEntry:
    shot_id: int
    t_sec: float
    image_ref: str
    embedding_index: int | None = None


@dataclass(frozen=True)
class FramePoolBuildResult:
    output_dir: str
    manifest_path: str
    shots_path: str
    shot_count: int
    non_dialogue_shot_count: int
    frame_count: int


@dataclass(frozen=True)
class QueryFramePoolResult:
    source: str
    frames_base64_png: tuple[str, ...]
    frame_times_sec: tuple[float, ...]
    shot_ids: tuple[int | None, ...]
