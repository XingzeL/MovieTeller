from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from frame_source import FrameSourceOptions
from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import (
    NarrationOptions,
    NarrationPolishOptions,
    NarrationSpeechOptions,
    Settings,
    SubtitleContextRetrieveOptions,
    settings_from_dict,
)
from pipeline_types import NarrationContext

from narration.narrate import narrate_segment_with_duration

from movie_pipeline.types import (
    MoviePipelineOptions,
    NarratedSegment,
    NarrationPolishDetails,
    NarrationSpeechDetails,
)
from subtitle_analysis import analyze_subtitle_file, result_to_dict
from subtitle_analysis.types import SubtitleAnalysisResult
from subtitle_context.index import subtitle_context_index_is_complete


def _resolve_subtitle_context_index_dir(
    srt_path: str,
    override: str | None,
) -> str | None:
    if override is not None:
        value = override.strip()
        if not value:
            return None
        return value if subtitle_context_index_is_complete(value) else None
    candidate = Path(str(Path(srt_path).with_suffix("")) + ".subtitle_context")
    if subtitle_context_index_is_complete(candidate):
        return str(candidate)
    return None


def _resolve_pipeline_settings(
    provider_override: str | None,
    *,
    frame_pool_manifest_override: str | None = None,
    polish_model_index_override: int | None = None,
):
    if (
        provider_override is None
        and frame_pool_manifest_override is None
        and polish_model_index_override is None
    ):
        settings = load_settings(require_narration=True)
        return settings
    flat = load_flat_dict()
    if provider_override is not None:
        flat["narration_provider"] = provider_override.strip().lower()
    if frame_pool_manifest_override is not None:
        flat["frame_pool_manifest"] = frame_pool_manifest_override.strip()
    if polish_model_index_override is not None:
        flat["narration_polish_model_index"] = int(polish_model_index_override)
    settings = settings_from_dict(flat)
    settings.require_api_key(settings.narration_provider)
    return settings


def _retrieve_context_texts_for_segment(
    *,
    subtitle_context_index_dir: str | None,
    segment_start_sec: float,
    query_text: str | None,
    settings: Settings,
    retrieve_options: SubtitleContextRetrieveOptions | None = None,
) -> tuple[str, ...]:
    if not subtitle_context_index_dir:
        return ()
    index_dir = Path(subtitle_context_index_dir)
    if not index_dir.is_dir():
        return ()
    query = str(query_text or "").strip()
    if not query:
        return ()
    from subtitle_context import retrieve_past_subtitle_context

    result = retrieve_past_subtitle_context(
        index_dir=str(index_dir),
        query_text=query,
        segment_start_sec=float(segment_start_sec),
        options=retrieve_options,
        settings=settings,
    )
    return tuple(
        str(chunk.text).strip()
        for chunk in result.retrieved_chunks
        if str(chunk.text).strip()
    )


def narrate_analysis_candidates(
    analysis: SubtitleAnalysisResult,
    *,
    video_path: str,
    subtitle_context_index_dir: str | None = None,
    max_candidates: int | None = None,
    narration_options: NarrationOptions | None = None,
    frame_source_options: FrameSourceOptions | None = None,
    subtitle_context_retrieve_options: SubtitleContextRetrieveOptions | None = None,
    polish_options: NarrationPolishOptions | None = None,
    speech_options: NarrationSpeechOptions | None = None,
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
    settings: Settings | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
) -> tuple[NarratedSegment, ...]:
    resolved_settings: Settings = (
        settings
        if settings is not None
        else _resolve_pipeline_settings(
            provider_slug,
            frame_pool_manifest_override=frame_pool_manifest,
            polish_model_index_override=polish_model_index,
        )
    )
    resolved_narration_options = narration_options or resolved_settings.narration_options(
        provider_slug=provider_slug,
        model=image_model,
        prompt_style=prompt_style,
        custom_prompt=custom_prompt,
    )
    call_narrator = narrator or narrate_segment_with_duration
    polish_enabled = (
        bool(polish)
        if polish is not None
        else (polish_options is not None or bool(getattr(resolved_settings, "narration_polish_enabled", False)))
    )
    resolved_polish_options = polish_options if polish_enabled else None
    if polish_enabled and resolved_polish_options is None:
        resolved_polish_options = resolved_settings.narration_polish_options(
            provider_slug=polish_provider_slug,
            model=polish_model,
            prompt_style=resolved_narration_options.prompt_style,
            target_wpm=polish_target_wpm,
            cefr_level=polish_cefr_level,
            strength=polish_strength,
            safety_margin_sec=polish_safety_margin_sec,
        )
    call_polisher: Callable[..., object] | None = polisher
    if polish_enabled and call_polisher is None:
        from narration_polish import polish_narration_text as _default_polisher

        call_polisher = _default_polisher
    speech_enabled = (
        bool(speech)
        if speech is not None
        else (speech_options is not None or bool(getattr(resolved_settings, "narration_speech_enabled", False)))
    )
    resolved_speech_options = speech_options if speech_enabled else None
    if speech_enabled and resolved_speech_options is None:
        resolved_speech_options = resolved_settings.narration_speech_options(
            provider_slug=speech_provider_slug,
            voice=speech_voice,
            rate=speech_rate,
            volume=speech_volume,
            pitch=speech_pitch,
            boundary=speech_boundary,
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
        narration_context = NarrationContext(
            segment_start_sec=seg.start_sec,
            segment_end_sec=seg.end_sec,
            prev_subtitle_text=seg.prev_subtitle_text,
            next_subtitle_text=seg.next_subtitle_text,
            retrieved_context_texts=_retrieve_context_texts_for_segment(
                subtitle_context_index_dir=subtitle_context_index_dir,
                segment_start_sec=seg.start_sec,
                query_text=seg.prev_subtitle_text,
                settings=resolved_settings,
                retrieve_options=subtitle_context_retrieve_options,
            ),
        )
        text, _duration = call_narrator(
            video_path,
            seg.start_sec,
            seg.end_sec,
            options=resolved_narration_options,
            frame_source_options=frame_source_options,
            prompt_style=resolved_narration_options.prompt_style,
            custom_prompt=resolved_narration_options.custom_prompt,
            image_model=resolved_narration_options.model,
            provider_slug=resolved_narration_options.provider_slug,
            settings=resolved_settings,
            timings_out=timings,
            narration_context=narration_context,
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
                options=resolved_polish_options,
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
                options=resolved_speech_options,
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


def _segments_to_payload(
    *,
    analysis: SubtitleAnalysisResult,
    narrated_segments: tuple[NarratedSegment, ...],
    speech_output_dir: str | None,
    subtitle_context_index_dir: str | None,
) -> dict[str, object]:
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
    payload["speechOutputDir"] = speech_output_dir
    payload["subtitleContextIndexDir"] = subtitle_context_index_dir
    return payload


def run_pipeline(
    *,
    srt_path: str,
    video_path: str,
    pipeline_options: MoviePipelineOptions,
    settings: Settings | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
    video_renderer: Callable[..., object] | None = None,
) -> dict[str, object]:
    resolved_settings = settings if settings is not None else load_settings(require_narration=True)
    analysis = analyze_subtitle_file(
        srt_path,
        video_path=video_path,
        video_duration_sec=pipeline_options.video_duration_sec,
        min_gap_sec=pipeline_options.min_gap_sec,
        subtitle_guard_sec=pipeline_options.subtitle_guard_sec,
        ffprobe_bin=pipeline_options.ffprobe_bin,
    )
    resolved_subtitle_context_index_dir = _resolve_subtitle_context_index_dir(
        srt_path,
        pipeline_options.subtitle_context_index_dir,
    )
    if pipeline_options.build_subtitle_context:
        from subtitle_context import build_subtitle_context_index

        resolved_subtitle_context_index_dir = (
            resolved_subtitle_context_index_dir
            or str(Path(srt_path).with_suffix("")) + ".subtitle_context"
        )
        build_subtitle_context_index(
            srt_path=srt_path,
            output_dir=resolved_subtitle_context_index_dir,
            options=pipeline_options.subtitle_context_build_options,
            settings=resolved_settings,
        )

    speech_requested = pipeline_options.speech_options is not None or pipeline_options.embed_video
    resolved_speech_output_dir = pipeline_options.speech_output_dir
    if resolved_speech_output_dir is None and speech_requested:
        resolved_speech_output_dir = str(Path(video_path).with_suffix("")) + ".narration_audio"

    resolved_frame_source_options = pipeline_options.frame_source_options or FrameSourceOptions(
        ffmpeg_bin=resolved_settings.ffmpeg_path,
        max_frames_per_segment=resolved_settings.max_frames_per_segment,
        max_edge_pixels=resolved_settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=resolved_settings.pool_miss_uniform_max_frames,
        allow_uniform_fallback=True,
    )
    narrated_segments = narrate_analysis_candidates(
        analysis,
        video_path=video_path,
        subtitle_context_index_dir=resolved_subtitle_context_index_dir,
        max_candidates=pipeline_options.max_candidates,
        narration_options=pipeline_options.narration_options,
        frame_source_options=resolved_frame_source_options,
        subtitle_context_retrieve_options=pipeline_options.subtitle_context_retrieve_options,
        polish_options=pipeline_options.polish_options,
        speech_options=pipeline_options.speech_options,
        speech=speech_requested,
        speech_output_dir=resolved_speech_output_dir,
        settings=resolved_settings,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
    )
    payload = _segments_to_payload(
        analysis=analysis,
        narrated_segments=narrated_segments,
        speech_output_dir=resolved_speech_output_dir,
        subtitle_context_index_dir=resolved_subtitle_context_index_dir,
    )
    if pipeline_options.embed_video:
        from narration_video import NarrationAudioSegment, render_narrated_video

        _default_renderer = video_renderer or render_narrated_video
        audio_segments = [seg for seg in narrated_segments if seg.speech is not None]
        if not audio_segments:
            raise RuntimeError("embed_video requires synthesized speech audio segments")
        output_path = pipeline_options.embed_output_path or (
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
            options=pipeline_options.video_options,
            settings=resolved_settings,
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
    build_subtitle_context: bool = False,
    subtitle_context_history_window_sec: float | None = None,
    subtitle_context_top_k: int | None = None,
    subtitle_context_chunk_cue_count: int | None = None,
    subtitle_context_chunk_stride: int | None = None,
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
    settings: Settings | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
    video_renderer: Callable[..., object] | None = None,
) -> dict[str, object]:
    """
    Compatibility wrapper around ``run_pipeline(...)``.

    Prefer constructing ``MoviePipelineOptions`` explicitly and calling
    ``run_pipeline(...)`` in new code.
    """
    resolved_settings = (
        settings
        if settings is not None
        else _resolve_pipeline_settings(
            provider_slug,
            frame_pool_manifest_override=frame_pool_manifest,
        )
    )
    narration_options = resolved_settings.narration_options(
        provider_slug=provider_slug,
        model=image_model,
        prompt_style=prompt_style,
        custom_prompt=custom_prompt,
    )
    polish_enabled = (
        bool(polish)
        if polish is not None
        else bool(getattr(resolved_settings, "narration_polish_enabled", False))
    )
    speech_enabled = bool(embed_video) or (
        bool(speech)
        if speech is not None
        else bool(getattr(resolved_settings, "narration_speech_enabled", False))
    )
    pipeline_options = MoviePipelineOptions(
        video_duration_sec=video_duration_sec,
        min_gap_sec=min_gap_sec,
        subtitle_guard_sec=subtitle_guard_sec,
        ffprobe_bin=ffprobe_bin,
        max_candidates=max_candidates,
        subtitle_context_index_dir=subtitle_context_index_dir,
        build_subtitle_context=build_subtitle_context,
        speech_output_dir=speech_output_dir,
        embed_video=embed_video,
        embed_output_path=embed_output_path,
        narration_options=narration_options,
        frame_source_options=FrameSourceOptions(
            ffmpeg_bin=resolved_settings.ffmpeg_path,
            max_frames_per_segment=resolved_settings.max_frames_per_segment,
            max_edge_pixels=resolved_settings.narration_frame_max_edge,
            pool_miss_uniform_max_frames=resolved_settings.pool_miss_uniform_max_frames,
            allow_uniform_fallback=True,
        ),
        subtitle_context_build_options=resolved_settings.subtitle_context_build_options(
            chunk_cue_count=subtitle_context_chunk_cue_count,
            chunk_stride=subtitle_context_chunk_stride,
        ),
        subtitle_context_retrieve_options=resolved_settings.subtitle_context_retrieve_options(
            history_window_sec=subtitle_context_history_window_sec,
            top_k=subtitle_context_top_k,
        ),
        polish_options=(
            resolved_settings.narration_polish_options(
                provider_slug=polish_provider_slug,
                model=polish_model,
                prompt_style=narration_options.prompt_style,
                target_wpm=polish_target_wpm,
                cefr_level=polish_cefr_level,
                strength=polish_strength,
                safety_margin_sec=polish_safety_margin_sec,
            )
            if polish_enabled
            else None
        ),
        speech_options=(
            resolved_settings.narration_speech_options(
                provider_slug=speech_provider_slug,
                voice=speech_voice,
                rate=speech_rate,
                volume=speech_volume,
                pitch=speech_pitch,
                boundary=speech_boundary,
            )
            if speech_enabled
            else None
        ),
        video_options=(
            resolved_settings.narration_video_options(
                background_audio_volume=background_audio_volume,
                speech_audio_volume=narration_audio_volume,
            )
            if embed_video
            else None
        ),
    )
    if pipeline_options.polish_options is not None and hasattr(resolved_settings, "require_api_key"):
        resolved_settings.require_api_key(pipeline_options.polish_options.provider_slug)
    return run_pipeline(
        srt_path=srt_path,
        video_path=video_path,
        pipeline_options=pipeline_options,
        settings=resolved_settings,
        narrator=narrator,
        polisher=polisher,
        synthesizer=synthesizer,
        video_renderer=video_renderer,
    )
