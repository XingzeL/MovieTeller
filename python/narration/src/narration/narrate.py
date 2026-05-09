from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable

from movieteller_config import load_settings

from narration.frames import (
    extract_frames_base64,
    ffprobe_path_for,
    segment_duration_sec,
)
from narration.prompts import build_system_message, build_user_text
from narration.story import generate_narration

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


def narrate_segment_with_duration(
    video_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
    *,
    prompt_style: str = "documentary",
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    settings: "Settings | None" = None,
    subprocess_run: Callable[..., Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
    timings_out: dict[str, Any] | None = None,
) -> tuple[str, float]:
    """
    Produce narration text and the segment duration (seconds) used for prompts and ffmpeg.

    If ``start_sec`` and ``end_sec`` are both ``None``, duration is from ffprobe on the full file.

    If ``timings_out`` is a dict, it is filled with ``extract_sec``, ``api_sec``, ``total_sec``
    (wall-clock seconds from :func:`time.perf_counter`), and ``frame_count`` (int).
    """
    cfg = settings if settings is not None else load_settings(require_narration=True)
    ffprobe = ffprobe_path_for(cfg.ffmpeg_path)
    duration = segment_duration_sec(
        video_path, start_sec, end_sec, ffprobe_bin=ffprobe
    )

    run = subprocess_run or __import__("subprocess").run
    t_extract0 = time.perf_counter()
    frames = extract_frames_base64(
        video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration,
        max_frames=cfg.max_frames_per_segment,
        ffmpeg_bin=cfg.ffmpeg_path,
        max_edge_pixels=cfg.narration_frame_max_edge,
        subprocess_run=run,
    )
    t_extract1 = time.perf_counter()

    slug = (provider_slug or cfg.narration_provider).strip().lower() or "openai"
    model = image_model or cfg.model_for_provider(slug)
    system_msg = build_system_message(prompt_style, custom_prompt)
    user_txt = build_user_text(
        duration_sec=duration,
        prompt_style=prompt_style,
        frame_count=len(frames),
    )

    t_api0 = time.perf_counter()
    text = generate_narration(
        system_message=system_msg,
        user_text=user_txt,
        frames_base64_png=frames,
        model=model,
        settings=cfg,
        provider_slug=provider_slug,
        client_factory=client_factory,
    )
    t_api1 = time.perf_counter()

    if timings_out is not None:
        extract_sec = t_extract1 - t_extract0
        api_sec = t_api1 - t_api0
        timings_out["extract_sec"] = extract_sec
        timings_out["api_sec"] = api_sec
        timings_out["total_sec"] = extract_sec + api_sec
        timings_out["frame_count"] = len(frames)

    return text, duration


def narrate_segment(
    video_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
    *,
    prompt_style: str = "documentary",
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    settings: "Settings | None" = None,
    subprocess_run: Callable[..., Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
    timings_out: dict[str, Any] | None = None,
) -> str:
    """Produce English narration using ffmpeg frames + an OpenAI-compatible multimodal API."""

    text, _ = narrate_segment_with_duration(
        video_path,
        start_sec,
        end_sec,
        prompt_style=prompt_style,
        custom_prompt=custom_prompt,
        image_model=image_model,
        provider_slug=provider_slug,
        settings=settings,
        subprocess_run=subprocess_run,
        client_factory=client_factory,
        timings_out=timings_out,
    )
    return text
