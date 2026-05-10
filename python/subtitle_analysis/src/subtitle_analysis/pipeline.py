from __future__ import annotations

from typing import Any, Callable

from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict

from narration.narrate import narrate_segment_with_duration

from subtitle_analysis.analyze import analyze_subtitle_file, result_to_dict
from subtitle_analysis.types import (
    NarratedSegment,
    NarrationPolishDetails,
    SubtitleAnalysisResult,
)


def _resolve_pipeline_settings(
    provider_override: str | None,
    *,
    polish_override: bool | None = None,
    polish_provider_override: str | None = None,
    polish_model_override: str | None = None,
    polish_model_index_override: int | None = None,
    polish_target_wpm_override: int | None = None,
    polish_cefr_level_override: str | None = None,
    polish_strength_override: str | None = None,
    polish_safety_margin_sec_override: float | None = None,
):
    if (
        provider_override is None
        and polish_override is None
        and polish_provider_override is None
        and polish_model_override is None
        and polish_model_index_override is None
        and polish_target_wpm_override is None
        and polish_cefr_level_override is None
        and polish_strength_override is None
        and polish_safety_margin_sec_override is None
    ):
        settings = load_settings(require_narration=True)
        if settings.narration_polish_enabled:
            settings.require_api_key(settings.polish_provider())
        return settings
    flat = load_flat_dict()
    if provider_override is not None:
        flat["narration_provider"] = provider_override.strip().lower()
    if polish_override is not None:
        flat["narration_polish_enabled"] = polish_override
    if polish_provider_override is not None:
        flat["narration_polish_provider"] = polish_provider_override.strip().lower()
    if polish_model_override is not None:
        flat["narration_polish_model"] = polish_model_override.strip()
    if polish_model_index_override is not None:
        flat["narration_polish_model_index"] = int(polish_model_index_override)
    if polish_target_wpm_override is not None:
        flat["narration_polish_target_wpm"] = int(polish_target_wpm_override)
    if polish_cefr_level_override is not None:
        flat["narration_polish_cefr_level"] = polish_cefr_level_override.strip().upper()
    if polish_strength_override is not None:
        flat["narration_polish_strength"] = polish_strength_override.strip().lower()
    if polish_safety_margin_sec_override is not None:
        flat["narration_polish_safety_margin_sec"] = float(
            polish_safety_margin_sec_override
        )
    settings = settings_from_dict(flat)
    settings.require_api_key(settings.narration_provider)
    if settings.narration_polish_enabled:
        settings.require_api_key(settings.polish_provider())
    return settings


def narrate_analysis_candidates(
    analysis: SubtitleAnalysisResult,
    *,
    video_path: str,
    max_candidates: int | None = None,
    prompt_style: str | None = None,
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    polish: bool | None = None,
    polish_provider_slug: str | None = None,
    polish_model: str | None = None,
    polish_model_index: int | None = None,
    polish_target_wpm: int | None = None,
    polish_cefr_level: str | None = None,
    polish_strength: str | None = None,
    polish_safety_margin_sec: float | None = None,
    settings: object | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
) -> tuple[NarratedSegment, ...]:
    resolved_settings = (
        settings
        if settings is not None
        else _resolve_pipeline_settings(
            provider_slug,
            polish_override=polish,
            polish_provider_override=polish_provider_slug,
            polish_model_override=polish_model,
            polish_model_index_override=polish_model_index,
            polish_target_wpm_override=polish_target_wpm,
            polish_cefr_level_override=polish_cefr_level,
            polish_strength_override=polish_strength,
            polish_safety_margin_sec_override=polish_safety_margin_sec,
        )
    )
    style = (
        prompt_style
        or str(getattr(resolved_settings, "default_prompt_style", "") or "documentary")
    )
    call_narrator = narrator or narrate_segment_with_duration
    polish_enabled = (
        bool(polish)
        if polish is not None
        else bool(getattr(resolved_settings, "narration_polish_enabled", False))
    )
    call_polisher: Callable[..., object] | None = polisher
    if polish_enabled and call_polisher is None:
        from narration_polish import polish_narration_text as _default_polisher

        call_polisher = _default_polisher

    candidates = analysis.narration_candidates
    if max_candidates is not None:
        candidates = candidates[: max(0, int(max_candidates))]

    out: list[NarratedSegment] = []
    for seg in candidates:
        timings: dict[str, Any] = {}
        text, _duration = call_narrator(
            video_path,
            seg.start_sec,
            seg.end_sec,
            prompt_style=style,
            custom_prompt=custom_prompt,
            image_model=image_model,
            provider_slug=provider_slug,
            settings=resolved_settings,
            timings_out=timings,
        )
        polish_details: NarrationPolishDetails | None = None
        speech_text = text
        if polish_enabled:
            if call_polisher is None:
                raise RuntimeError("Narration polisher is not available")
            polished = call_polisher(
                text,
                seg.duration_sec,
                target_wpm=polish_target_wpm,
                cefr_level=polish_cefr_level,
                strength=polish_strength,
                safety_margin_sec=polish_safety_margin_sec,
                provider_slug=polish_provider_slug,
                model=polish_model,
                settings=resolved_settings,
            )
            speech_text = str(getattr(polished, "polished_text"))
            polish_details = NarrationPolishDetails(
                text=speech_text,
                segment_duration_sec=float(getattr(polished, "segment_duration_sec")),
                target_duration_sec=float(getattr(polished, "target_duration_sec")),
                safety_margin_sec=float(getattr(polished, "safety_margin_sec")),
                speaking_rate_wpm=int(getattr(polished, "speaking_rate_wpm")),
                target_word_count=int(getattr(polished, "target_word_count")),
                original_word_count=int(getattr(polished, "original_word_count")),
                polished_word_count=int(getattr(polished, "polished_word_count")),
                estimated_original_duration_sec=float(
                    getattr(polished, "estimated_original_duration_sec")
                ),
                estimated_polished_duration_sec=float(
                    getattr(polished, "estimated_polished_duration_sec")
                ),
                cefr_level=str(getattr(polished, "cefr_level")),
                strength=str(getattr(polished, "strength")),
                provider=str(getattr(polished, "provider")),
                model=str(getattr(polished, "model")),
                timing_api_sec=(
                    float(getattr(polished, "timing_api_sec"))
                    if getattr(polished, "timing_api_sec", None) is not None
                    else None
                ),
            )
        out.append(
            NarratedSegment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                narration_text=text,
                prev_subtitle_text=seg.prev_subtitle_text,
                next_subtitle_text=seg.next_subtitle_text,
                speech_text=speech_text,
                polish=polish_details,
                timing_extract_sec=(
                    float(timings["extract_sec"]) if "extract_sec" in timings else None
                ),
                timing_api_sec=(
                    float(timings["api_sec"]) if "api_sec" in timings else None
                ),
                timing_total_sec=(
                    float(timings["total_sec"]) if "total_sec" in timings else None
                ),
                frame_count=int(timings["frame_count"])
                if "frame_count" in timings
                else None,
            )
        )
    return tuple(out)


def analyze_and_narrate(
    *,
    srt_path: str,
    video_path: str,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
    ffprobe_bin: str = "ffprobe",
    max_candidates: int | None = None,
    prompt_style: str | None = None,
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    polish: bool | None = None,
    polish_provider_slug: str | None = None,
    polish_model: str | None = None,
    polish_model_index: int | None = None,
    polish_target_wpm: int | None = None,
    polish_cefr_level: str | None = None,
    polish_strength: str | None = None,
    polish_safety_margin_sec: float | None = None,
    settings: object | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
) -> dict[str, object]:
    analysis = analyze_subtitle_file(
        srt_path,
        video_path=video_path,
        video_duration_sec=video_duration_sec,
        min_gap_sec=min_gap_sec,
        subtitle_guard_sec=subtitle_guard_sec,
        ffprobe_bin=ffprobe_bin,
    )
    narrated_segments = narrate_analysis_candidates(
        analysis,
        video_path=video_path,
        max_candidates=max_candidates,
        prompt_style=prompt_style,
        custom_prompt=custom_prompt,
        image_model=image_model,
        provider_slug=provider_slug,
        polish=polish,
        polish_provider_slug=polish_provider_slug,
        polish_model=polish_model,
        polish_model_index=polish_model_index,
        polish_target_wpm=polish_target_wpm,
        polish_cefr_level=polish_cefr_level,
        polish_strength=polish_strength,
        polish_safety_margin_sec=polish_safety_margin_sec,
        settings=settings,
        narrator=narrator,
        polisher=polisher,
    )
    payload = result_to_dict(analysis)
    payload["narratedSegments"] = [
        {
            "startSec": seg.start_sec,
            "endSec": seg.end_sec,
            "durationSec": seg.duration_sec,
            "text": seg.narration_text,
            "speechText": seg.final_text,
            "prevSubtitleText": seg.prev_subtitle_text,
            "nextSubtitleText": seg.next_subtitle_text,
            "polish": (
                {
                    "text": seg.polish.text,
                    "segmentDurationSec": seg.polish.segment_duration_sec,
                    "targetDurationSec": seg.polish.target_duration_sec,
                    "safetyMarginSec": seg.polish.safety_margin_sec,
                    "speakingRateWpm": seg.polish.speaking_rate_wpm,
                    "targetWordCount": seg.polish.target_word_count,
                    "originalWordCount": seg.polish.original_word_count,
                    "polishedWordCount": seg.polish.polished_word_count,
                    "estimatedOriginalDurationSec": seg.polish.estimated_original_duration_sec,
                    "estimatedPolishedDurationSec": seg.polish.estimated_polished_duration_sec,
                    "cefrLevel": seg.polish.cefr_level,
                    "strength": seg.polish.strength,
                    "provider": seg.polish.provider,
                    "model": seg.polish.model,
                    "fitsDuration": seg.polish.fits_duration,
                    "timingApiSec": seg.polish.timing_api_sec,
                }
                if seg.polish is not None
                else None
            ),
            "timingExtractSec": seg.timing_extract_sec,
            "timingApiSec": seg.timing_api_sec,
            "timingTotalSec": seg.timing_total_sec,
            "frameCount": seg.frame_count,
        }
        for seg in narrated_segments
    ]
    return payload
