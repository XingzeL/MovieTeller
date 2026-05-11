from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict

from narration.narrate import narrate_segment_with_duration

from subtitle_analysis.analyze import analyze_subtitle_file, result_to_dict
from subtitle_analysis.types import (
    NarratedSegment,
    NarrationPolishDetails,
    NarrationSpeechDetails,
    SubtitleAnalysisResult,
)


def _resolve_subtitle_context_index_dir(
    srt_path: str,
    override: str | None,
) -> str | None:
    if override is not None:
        value = override.strip()
        return value or None
    candidate = Path(str(Path(srt_path).with_suffix("")) + ".subtitle_context")
    if candidate.is_dir():
        return str(candidate)
    return None


def _resolve_pipeline_settings(
    provider_override: str | None,
    *,
    frame_pool_manifest_override: str | None = None,
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
        and frame_pool_manifest_override is None
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
    if frame_pool_manifest_override is not None:
        flat["frame_pool_manifest"] = frame_pool_manifest_override.strip()
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
    subtitle_context_index_dir: str | None = None,
    max_candidates: int | None = None,
    prompt_style: str | None = None,
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    frame_pool_manifest: str | None = None,
    polish: bool | None = None,
    polish_provider_slug: str | None = None,
    polish_model: str | None = None,
    polish_model_index: int | None = None,
    polish_target_wpm: int | None = None,
    polish_cefr_level: str | None = None,
    polish_strength: str | None = None,
    polish_safety_margin_sec: float | None = None,
    speech: bool | None = None,
    speech_provider_slug: str | None = None,
    speech_voice: str | None = None,
    speech_rate: str | None = None,
    speech_volume: str | None = None,
    speech_pitch: str | None = None,
    speech_boundary: str | None = None,
    speech_output_dir: str | None = None,
    settings: object | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
) -> tuple[NarratedSegment, ...]:
    resolved_settings = (
        settings
        if settings is not None
        else _resolve_pipeline_settings(
            provider_slug,
            frame_pool_manifest_override=frame_pool_manifest,
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
    speech_enabled = (
        bool(speech)
        if speech is not None
        else bool(getattr(resolved_settings, "narration_speech_enabled", False))
    )
    call_synthesizer: Callable[..., object] | None = synthesizer
    if speech_enabled and call_synthesizer is None:
        from narration_speech import synthesize_narration_text as _default_synthesizer

        call_synthesizer = _default_synthesizer
    speech_dir = Path(speech_output_dir) if speech_output_dir else None
    if speech_dir is not None:
        speech_dir.mkdir(parents=True, exist_ok=True)

    candidates = analysis.narration_candidates
    if max_candidates is not None:
        candidates = candidates[: max(0, int(max_candidates))]

    out: list[NarratedSegment] = []
    for idx, seg in enumerate(candidates, start=1):
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
            subtitle_context_input={
                "segment_start_sec": seg.start_sec,
                "segment_end_sec": seg.end_sec,
                "prev_subtitle_text": seg.prev_subtitle_text,
                "next_subtitle_text": seg.next_subtitle_text,
                "index_dir": subtitle_context_index_dir,
            },
        )
        polish_details: NarrationPolishDetails | None = None
        speech_details: NarrationSpeechDetails | None = None
        speech_text = text
        if polish_enabled:
            if call_polisher is None:
                raise RuntimeError("Narration polisher is not available")
            polished = call_polisher(
                text,
                seg.duration_sec,
                prompt_style=style,
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
        if speech_enabled:
            if call_synthesizer is None:
                raise RuntimeError("Narration speech synthesizer is not available")
            if speech_dir is None:
                raise ValueError("speech_output_dir is required when speech synthesis is enabled")
            filename = (
                f"segment_{idx:03d}_"
                f"{round(seg.start_sec * 1000):08d}_"
                f"{round(seg.end_sec * 1000):08d}.mp3"
            )
            audio_path = speech_dir / filename
            metadata_path = audio_path.with_suffix(audio_path.suffix + ".jsonl")
            target_duration_sec = (
                polish_details.target_duration_sec
                if polish_details is not None
                else seg.duration_sec
            )
            spoken = call_synthesizer(
                speech_text,
                seg.duration_sec,
                output_path=str(audio_path),
                metadata_path=str(metadata_path),
                target_duration_sec=target_duration_sec,
                provider_slug=speech_provider_slug,
                voice=speech_voice,
                rate=speech_rate,
                volume=speech_volume,
                pitch=speech_pitch,
                boundary=speech_boundary,
                settings=resolved_settings,
            )
            speech_details = NarrationSpeechDetails(
                text=str(getattr(spoken, "text")),
                audio_path=str(getattr(spoken, "audio_path")),
                metadata_path=getattr(spoken, "metadata_path", None),
                segment_duration_sec=float(getattr(spoken, "segment_duration_sec")),
                target_duration_sec=float(getattr(spoken, "target_duration_sec")),
                raw_duration_sec=float(getattr(spoken, "raw_duration_sec")),
                audio_duration_sec=float(getattr(spoken, "audio_duration_sec")),
                provider=str(getattr(spoken, "provider")),
                voice=str(getattr(spoken, "voice")),
                rate=str(getattr(spoken, "rate")),
                volume=str(getattr(spoken, "volume")),
                pitch=str(getattr(spoken, "pitch")),
                boundary=str(getattr(spoken, "boundary")),
                fit_applied=bool(getattr(spoken, "fit_applied")),
                timing_tts_sec=(
                    float(getattr(spoken, "timing_tts_sec"))
                    if getattr(spoken, "timing_tts_sec", None) is not None
                    else None
                ),
                timing_fit_sec=(
                    float(getattr(spoken, "timing_fit_sec"))
                    if getattr(spoken, "timing_fit_sec", None) is not None
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
                speech=speech_details,
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
    subtitle_context_index_dir: str | None = None,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
    ffprobe_bin: str = "ffprobe",
    max_candidates: int | None = None,
    prompt_style: str | None = None,
    custom_prompt: str = "",
    image_model: str | None = None,
    provider_slug: str | None = None,
    frame_pool_manifest: str | None = None,
    polish: bool | None = None,
    polish_provider_slug: str | None = None,
    polish_model: str | None = None,
    polish_model_index: int | None = None,
    polish_target_wpm: int | None = None,
    polish_cefr_level: str | None = None,
    polish_strength: str | None = None,
    polish_safety_margin_sec: float | None = None,
    speech: bool | None = None,
    speech_provider_slug: str | None = None,
    speech_voice: str | None = None,
    speech_rate: str | None = None,
    speech_volume: str | None = None,
    speech_pitch: str | None = None,
    speech_boundary: str | None = None,
    speech_output_dir: str | None = None,
    embed_video: bool = False,
    embed_output_path: str | None = None,
    background_audio_volume: float | None = None,
    narration_audio_volume: float | None = None,
    settings: object | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
    video_renderer: Callable[..., object] | None = None,
) -> dict[str, object]:
    analysis = analyze_subtitle_file(
        srt_path,
        video_path=video_path,
        video_duration_sec=video_duration_sec,
        min_gap_sec=min_gap_sec,
        subtitle_guard_sec=subtitle_guard_sec,
        ffprobe_bin=ffprobe_bin,
    )
    resolved_speech_output_dir = speech_output_dir
    speech_requested = bool(speech) or embed_video
    if not speech_requested and settings is not None:
        speech_requested = bool(getattr(settings, "narration_speech_enabled", False))
    if not speech_requested and settings is None:
        speech_requested = bool(load_settings().narration_speech_enabled)
    if resolved_speech_output_dir is None and speech_requested:
        resolved_speech_output_dir = str(Path(video_path).with_suffix("")) + ".narration_audio"
    resolved_subtitle_context_index_dir = _resolve_subtitle_context_index_dir(
        srt_path,
        subtitle_context_index_dir,
    )

    narrated_segments = narrate_analysis_candidates(
        analysis,
        video_path=video_path,
        subtitle_context_index_dir=resolved_subtitle_context_index_dir,
        max_candidates=max_candidates,
        prompt_style=prompt_style,
        custom_prompt=custom_prompt,
        image_model=image_model,
        provider_slug=provider_slug,
        frame_pool_manifest=frame_pool_manifest,
        polish=polish,
        polish_provider_slug=polish_provider_slug,
        polish_model=polish_model,
        polish_model_index=polish_model_index,
        polish_target_wpm=polish_target_wpm,
        polish_cefr_level=polish_cefr_level,
        polish_strength=polish_strength,
        polish_safety_margin_sec=polish_safety_margin_sec,
        speech=(True if embed_video else speech),
        speech_provider_slug=speech_provider_slug,
        speech_voice=speech_voice,
        speech_rate=speech_rate,
        speech_volume=speech_volume,
        speech_pitch=speech_pitch,
        speech_boundary=speech_boundary,
        speech_output_dir=resolved_speech_output_dir,
        settings=settings,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
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
            "speech": (
                {
                    "text": seg.speech.text,
                    "audioPath": seg.speech.audio_path,
                    "metadataPath": seg.speech.metadata_path,
                    "segmentDurationSec": seg.speech.segment_duration_sec,
                    "targetDurationSec": seg.speech.target_duration_sec,
                    "rawDurationSec": seg.speech.raw_duration_sec,
                    "audioDurationSec": seg.speech.audio_duration_sec,
                    "durationDeltaSec": seg.speech.duration_delta_sec,
                    "provider": seg.speech.provider,
                    "voice": seg.speech.voice,
                    "rate": seg.speech.rate,
                    "volume": seg.speech.volume,
                    "pitch": seg.speech.pitch,
                    "boundary": seg.speech.boundary,
                    "fitApplied": seg.speech.fit_applied,
                    "fitsDuration": seg.speech.fits_duration,
                    "timingTtsSec": seg.speech.timing_tts_sec,
                    "timingFitSec": seg.speech.timing_fit_sec,
                }
                if seg.speech is not None
                else None
            ),
            "timingExtractSec": seg.timing_extract_sec,
            "timingApiSec": seg.timing_api_sec,
            "timingTotalSec": seg.timing_total_sec,
            "frameCount": seg.frame_count,
        }
        for seg in narrated_segments
    ]
    payload["speechOutputDir"] = resolved_speech_output_dir
    payload["subtitleContextIndexDir"] = resolved_subtitle_context_index_dir
    if embed_video:
        from narration_video import NarrationAudioSegment, render_narrated_video

        _default_renderer = video_renderer or render_narrated_video
        audio_segments = [seg for seg in narrated_segments if seg.speech is not None]
        if not audio_segments:
            raise RuntimeError("embed_video requires synthesized speech audio segments")
        output_path = embed_output_path or (
            str(Path(video_path).with_suffix("")) + ".narrated.mp4"
        )
        render_segments = [
            NarrationAudioSegment(
                start_sec=seg.start_sec,
                end_sec=seg.end_sec,
                audio_path=seg.speech.audio_path,
            )
            for seg in audio_segments
        ]
        render_result = _default_renderer(
            video_path,
            render_segments,
            output_path=output_path,
            background_audio_volume=background_audio_volume,
            speech_audio_volume=narration_audio_volume,
            settings=settings,
        )
        payload["renderedVideo"] = {
            "videoPath": str(getattr(render_result, "video_path")),
            "outputPath": str(getattr(render_result, "output_path")),
            "segmentCount": int(getattr(render_result, "segment_count")),
            "videoDurationSec": float(getattr(render_result, "video_duration_sec")),
            "backgroundAudioVolume": float(
                getattr(render_result, "background_audio_volume")
            ),
            "speechAudioVolume": float(getattr(render_result, "speech_audio_volume")),
            "timingRenderSec": (
                float(getattr(render_result, "timing_render_sec"))
                if getattr(render_result, "timing_render_sec", None) is not None
                else None
            ),
        }
    else:
        payload["renderedVideo"] = None
    return payload
