from __future__ import annotations

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any, Callable, Mapping

from media_utils import ffprobe_path_for, segment_duration_sec
from movieteller_config import load_settings

from narration.frames import extract_frames_base64
from narration.prompts import build_system_message, build_user_text
from narration.story import generate_narration

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


@dataclass(frozen=True)
class SubtitleNarrationContext:
    segment_start_sec: float
    segment_end_sec: float
    prev_subtitle_text: str | None = None
    next_subtitle_text: str | None = None
    index_dir: str | None = None


def _window_bounds(
    *,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
) -> tuple[float, float]:
    if start_sec is None or end_sec is None:
        return 0.0, duration_sec
    return start_sec, end_sec


def _extract_frames_for_narration(
    *,
    cfg: "Settings",
    video_path: str,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    subprocess_run: Callable[..., Any],
    timings_out: dict[str, Any] | None = None,
) -> list[str]:
    manifest_path = str(getattr(cfg, "frame_pool_manifest", "") or "").strip()
    if manifest_path:
        try:
            from video_frame_pool import PoolWindowMiss, query_frame_pool
        except ImportError as exc:
            raise RuntimeError(
                "frame_pool_manifest is configured but video_frame_pool is not installed"
            ) from exc
        win_start, win_end = _window_bounds(
            start_sec=start_sec,
            end_sec=end_sec,
            duration_sec=duration_sec,
        )
        try:
            query = query_frame_pool(
                manifest_path=manifest_path,
                start_sec=win_start,
                end_sec=win_end,
                budget=cfg.max_frames_per_segment,
                settings=cfg,
            )
        except PoolWindowMiss:
            if timings_out is not None:
                timings_out["frame_source"] = "uniform_fallback"
            return extract_frames_base64(
                video_path,
                start_sec=start_sec,
                end_sec=end_sec,
                duration_sec=duration_sec,
                max_frames=cfg.pool_miss_uniform_max_frames,
                ffmpeg_bin=cfg.ffmpeg_path,
                max_edge_pixels=cfg.narration_frame_max_edge,
                subprocess_run=subprocess_run,
            )
        if timings_out is not None:
            timings_out["frame_source"] = "pool"
            timings_out["frame_times_sec"] = list(query.frame_times_sec)
            timings_out["frame_shot_ids"] = list(query.shot_ids)
        return list(query.frames_base64_png)

    if timings_out is not None:
        timings_out["frame_source"] = "uniform"
    return extract_frames_base64(
        video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration_sec,
        max_frames=cfg.max_frames_per_segment,
        ffmpeg_bin=cfg.ffmpeg_path,
        max_edge_pixels=cfg.narration_frame_max_edge,
        subprocess_run=subprocess_run,
    )


def _coerce_subtitle_context_input(
    value: SubtitleNarrationContext | Mapping[str, Any] | object | None,
) -> SubtitleNarrationContext | None:
    if value is None:
        return None
    if isinstance(value, SubtitleNarrationContext):
        return value
    if isinstance(value, Mapping):
        return SubtitleNarrationContext(
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
            index_dir=(str(value["index_dir"]) if value.get("index_dir") is not None else None),
        )
    return SubtitleNarrationContext(
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
        index_dir=(
            str(getattr(value, "index_dir"))
            if getattr(value, "index_dir", None) is not None
            else None
        ),
    )


def _retrieve_subtitle_context_texts(
    *,
    cfg: "Settings",
    subtitle_context_input: SubtitleNarrationContext | None,
    retriever: Callable[..., Any] | None,
    timings_out: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    if subtitle_context_input is None:
        return ()
    index_dir = str(subtitle_context_input.index_dir or "").strip()
    query_text = str(subtitle_context_input.prev_subtitle_text or "").strip()
    if not index_dir or not query_text:
        return ()
    call_retriever = retriever
    if call_retriever is None:
        from subtitle_context import retrieve_past_subtitle_context as _default_retriever

        call_retriever = _default_retriever
    result = call_retriever(
        index_dir=index_dir,
        query_text=query_text,
        segment_start_sec=float(subtitle_context_input.segment_start_sec),
        settings=cfg,
    )
    chunks = tuple(str(chunk.text).strip() for chunk in result.retrieved_chunks if str(chunk.text).strip())
    if timings_out is not None:
        timings_out["subtitle_context_index_dir"] = index_dir
        timings_out["subtitle_context_chunk_count"] = len(chunks)
    return chunks


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
    subtitle_context_input: SubtitleNarrationContext | Mapping[str, Any] | object | None = None,
    subtitle_context_retriever: Callable[..., Any] | None = None,
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
    frames = _extract_frames_for_narration(
        cfg=cfg,
        video_path=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration,
        subprocess_run=run,
        timings_out=timings_out,
    )
    t_extract1 = time.perf_counter()

    slug = (provider_slug or cfg.narration_provider).strip().lower() or "openai"
    model = image_model or cfg.model_for_provider(slug)
    system_msg = build_system_message(prompt_style, custom_prompt)
    subtitle_ctx = _coerce_subtitle_context_input(subtitle_context_input)
    retrieved_context_texts = _retrieve_subtitle_context_texts(
        cfg=cfg,
        subtitle_context_input=subtitle_ctx,
        retriever=subtitle_context_retriever,
        timings_out=timings_out,
    )
    user_txt = build_user_text(
        duration_sec=duration,
        prompt_style=prompt_style,
        frame_count=len(frames),
        prev_subtitle_text=(
            subtitle_ctx.prev_subtitle_text if subtitle_ctx is not None else None
        ),
        next_subtitle_text=(
            subtitle_ctx.next_subtitle_text if subtitle_ctx is not None else None
        ),
        retrieved_context_texts=retrieved_context_texts,
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
    subtitle_context_input: SubtitleNarrationContext | Mapping[str, Any] | object | None = None,
    subtitle_context_retriever: Callable[..., Any] | None = None,
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
        subtitle_context_input=subtitle_context_input,
        subtitle_context_retriever=subtitle_context_retriever,
    )
    return text
