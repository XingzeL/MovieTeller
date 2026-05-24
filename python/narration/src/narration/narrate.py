from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Mapping

from frame_source import FrameRequest, FrameSourceOptions, get_frames_for_segment
from media_utils import ffprobe_path_for, segment_duration_sec
from movieteller_config import load_settings
from movieteller_config.schema import NarrationOptions
from movieteller_logging import emit_event
from movieteller_logging import events as log_events
from pipeline_types import FrameBatch, NarrationContext, NarrationResult

from narration.prompts import build_system_message, build_user_text
from narration.story import generate_narration

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


def _window_bounds(
    *,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
) -> tuple[float, float]:
    if start_sec is None or end_sec is None:
        return 0.0, duration_sec
    return start_sec, end_sec


def _coerce_narration_context(
    value: NarrationContext | Mapping[str, Any] | object | None,
) -> NarrationContext | None:
    if value is None:
        return None
    if isinstance(value, NarrationContext):
        return value
    if isinstance(value, Mapping):
        return NarrationContext(
            segment_start_sec=float(value["segment_start_sec"]),
            segment_end_sec=float(value["segment_end_sec"]),
            prev_subtitle_text=(
                str(value["prev_subtitle_text"])
                if value.get("prev_subtitle_text") is not None
                else None
            ),
            next_subtitle_text=(
                str(value["next_subtitle_text"])
                if value.get("next_subtitle_text") is not None
                else None
            ),
            retrieved_context_texts=tuple(
                str(item).strip()
                for item in value.get("retrieved_context_texts", ())
                if str(item).strip()
            ),
        )
    return NarrationContext(
        segment_start_sec=float(getattr(value, "segment_start_sec")),
        segment_end_sec=float(getattr(value, "segment_end_sec")),
        prev_subtitle_text=(
            str(getattr(value, "prev_subtitle_text"))
            if getattr(value, "prev_subtitle_text", None) is not None
            else None
        ),
        next_subtitle_text=(
            str(getattr(value, "next_subtitle_text"))
            if getattr(value, "next_subtitle_text", None) is not None
            else None
        ),
        retrieved_context_texts=tuple(
            str(item).strip()
            for item in getattr(value, "retrieved_context_texts", ())
            if str(item).strip()
        ),
    )


def narrate_from_frames(
    *,
    frames: FrameBatch,
    context: NarrationContext | Mapping[str, Any] | object | None = None,
    options: NarrationOptions,
    settings: "Settings",
    client_factory: Callable[..., Any] | None = None,
) -> NarrationResult:
    system_msg = build_system_message(
        options.prompt_style,
        options.custom_prompt,
    )
    narration_ctx = _coerce_narration_context(context)
    user_txt = build_user_text(
        duration_sec=frames.duration_sec,
        prompt_style=options.prompt_style,
        frame_count=len(frames.frames_base64_png),
        prev_subtitle_text=(
            narration_ctx.prev_subtitle_text if narration_ctx is not None else None
        ),
        next_subtitle_text=(
            narration_ctx.next_subtitle_text if narration_ctx is not None else None
        ),
        retrieved_context_texts=(
            narration_ctx.retrieved_context_texts if narration_ctx is not None else ()
        ),
    )

    t_api0 = time.perf_counter()
    text = generate_narration(
        system_message=system_msg,
        user_text=user_txt,
        frames_base64_png=list(frames.frames_base64_png),
        settings=settings,
        client_factory=client_factory,
    )
    api_sec = time.perf_counter() - t_api0
    return NarrationResult(
        text=text,
        duration_sec=float(frames.duration_sec),
        frame_count=len(frames.frames_base64_png),
        frame_source=str(frames.source),
        timing_api_sec=api_sec,
        timing_total_sec=api_sec,
    )


def narrate_segment_with_duration(
    video_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
    *,
    options: NarrationOptions,
    frame_source_options: FrameSourceOptions,
    settings: "Settings",
    subprocess_run: Callable[..., Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
    timings_out: dict[str, Any] | None = None,
    narration_context: NarrationContext | Mapping[str, Any] | object | None = None,
) -> tuple[str, float]:
    """
    Produce narration text and the segment duration (seconds) used for prompts and ffmpeg.

    If ``start_sec`` and ``end_sec`` are both ``None``, duration is from ffprobe on the full file.

    If ``timings_out`` is a dict, it is filled with ``extract_sec``, ``api_sec``, ``total_sec``
    (wall-clock seconds from :func:`time.perf_counter`), and ``frame_count`` (int).
    """
    ffprobe = ffprobe_path_for(settings.ffmpeg_path)
    duration = segment_duration_sec(
        video_path, start_sec, end_sec, ffprobe_bin=ffprobe
    )

    run = subprocess_run or __import__("subprocess").run
    t_extract0 = time.perf_counter()
    manifest_path = str(getattr(settings, "frame_pool_manifest", "") or "").strip()
    strategy = "frame_pool" if manifest_path else "uniform"
    win_start, win_end = _window_bounds(
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration,
    )
    frames = get_frames_for_segment(
        FrameRequest(
            video_path=video_path,
            start_sec=(win_start if strategy == "frame_pool" else start_sec),
            end_sec=(win_end if strategy == "frame_pool" else end_sec),
            duration_sec=duration,
            strategy=strategy,
            frame_pool_manifest=(manifest_path or None),
        ),
        options=frame_source_options,
        settings=settings,
        subprocess_run=run,
    )
    emit_event(
        log_events.NARRATION_FRAMES_SELECTED,
        source=frames.source,
        win_start=win_start,
        win_end=win_end,
        duration_sec=frames.duration_sec,
        frames=len(frames.frames_base64_png),
    )
    t_extract1 = time.perf_counter()
    result = narrate_from_frames(
        frames=frames,
        context=narration_context,
        options=options,
        settings=settings,
        client_factory=client_factory,
    )

    if timings_out is not None:
        extract_sec = t_extract1 - t_extract0
        api_sec = float(result.timing_api_sec or 0.0)
        timings_out["extract_sec"] = extract_sec
        timings_out["api_sec"] = api_sec
        timings_out["total_sec"] = extract_sec + api_sec
        timings_out["frame_count"] = result.frame_count
        timings_out["frame_source"] = result.frame_source
        timings_out["frame_times_sec"] = list(frames.frame_times_sec)
        if frames.shot_ids is not None:
            timings_out["frame_shot_ids"] = list(frames.shot_ids)

    return result.text, duration


def narrate_segment(
    video_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
    *,
    options: NarrationOptions,
    frame_source_options: FrameSourceOptions,
    settings: "Settings",
    subprocess_run: Callable[..., Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
    timings_out: dict[str, Any] | None = None,
    narration_context: NarrationContext | Mapping[str, Any] | object | None = None,
) -> str:
    """Produce English narration using ffmpeg frames + an OpenAI-compatible multimodal API."""

    text, _ = narrate_segment_with_duration(
        video_path,
        start_sec,
        end_sec,
        options=options,
        frame_source_options=frame_source_options,
        settings=settings,
        subprocess_run=subprocess_run,
        client_factory=client_factory,
        timings_out=timings_out,
        narration_context=narration_context,
    )
    return text
