from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pipeline_types import FrameBatch
from video_frame_pool import PoolWindowMiss, query_frame_pool_as_frame_batch

from frame_source.uniform import sample_uniform_frames


@dataclass(frozen=True)
class FrameRequest:
    video_path: str
    start_sec: float | None
    end_sec: float | None
    duration_sec: float
    strategy: Literal["uniform", "frame_pool"]
    frame_pool_manifest: str | None = None


@dataclass(frozen=True)
class FrameSourceOptions:
    ffmpeg_bin: str
    max_frames_per_segment: int
    max_edge_pixels: int
    pool_miss_uniform_max_frames: int = 6
    allow_uniform_fallback: bool = True


def get_frames_for_segment(
    request: FrameRequest,
    *,
    options: FrameSourceOptions,
    settings: object | None = None,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> FrameBatch:
    if request.strategy == "uniform":
        return sample_uniform_frames(
            video_path=request.video_path,
            start_sec=request.start_sec,
            end_sec=request.end_sec,
            duration_sec=request.duration_sec,
            ffmpeg_bin=options.ffmpeg_bin,
            max_frames=options.max_frames_per_segment,
            max_edge_pixels=options.max_edge_pixels,
            subprocess_run=subprocess_run,
        )
    if request.strategy != "frame_pool":
        raise ValueError(f"Unsupported frame strategy: {request.strategy}")
    manifest_path = str(request.frame_pool_manifest or "").strip()
    if not manifest_path:
        raise ValueError("frame_pool_manifest is required for strategy='frame_pool'")
    if request.start_sec is None or request.end_sec is None:
        raise ValueError("frame_pool strategy requires concrete start_sec and end_sec")
    try:
        return query_frame_pool_as_frame_batch(
            manifest_path=manifest_path,
            start_sec=request.start_sec,
            end_sec=request.end_sec,
            duration_sec=request.duration_sec,
            budget=options.max_frames_per_segment,
            settings=settings,
        )
    except PoolWindowMiss:
        if not options.allow_uniform_fallback:
            raise
        batch = sample_uniform_frames(
            video_path=request.video_path,
            start_sec=request.start_sec,
            end_sec=request.end_sec,
            duration_sec=request.duration_sec,
            ffmpeg_bin=options.ffmpeg_bin,
            max_frames=options.pool_miss_uniform_max_frames,
            max_edge_pixels=options.max_edge_pixels,
            subprocess_run=subprocess_run,
        )
        return FrameBatch(
            frames_base64_png=batch.frames_base64_png,
            frame_times_sec=batch.frame_times_sec,
            duration_sec=batch.duration_sec,
            source="uniform_fallback",
            shot_ids=batch.shot_ids,
        )
