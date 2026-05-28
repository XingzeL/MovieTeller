"""Build runtime option objects from :class:`Settings` (keeps schema dataclasses declarative)."""

from __future__ import annotations

from movieteller_config.schema import (
    FramePoolBuildOptions,
    NarrationOptions,
    NarrationPolishOptions,
    NarrationSpeechOptions,
    NarrationVideoOptions,
    Settings,
    SubtitleContextBuildOptions,
    SubtitleContextRetrieveOptions,
    SubtitleExtractionOptions,
    _none_if_empty,
)


def build_narration_options(
    settings: Settings,
    *,
    prompt_style: str | None = None,
    custom_prompt: str = "",
    output_language: str | None = None,
) -> NarrationOptions:
    resolved_prompt_style = (
        str(prompt_style or settings.default_prompt_style).strip() or "documentary"
    )
    return NarrationOptions(
        prompt_style=resolved_prompt_style,
        custom_prompt=str(custom_prompt or ""),
        output_language=str(output_language or "en").strip() or "en",
    )


def build_narration_polish_options(
    settings: Settings,
    *,
    model: str | None = None,
    prompt_style: str | None = None,
    target_wpm: int | None = None,
    cefr_level: str | None = None,
    strength: str | None = None,
    safety_margin_sec: float | None = None,
    output_language: str | None = None,
) -> NarrationPolishOptions:
    resolved_model = str(model or settings.default_model_for_capability("polish")).strip()
    if not resolved_model:
        raise ValueError("narration polish model is empty")
    resolved_prompt_style = (
        str(prompt_style or settings.default_prompt_style).strip() or "documentary"
    )
    return NarrationPolishOptions(
        model=resolved_model,
        prompt_style=resolved_prompt_style,
        target_wpm=max(
            1,
            int(
                target_wpm
                if target_wpm is not None
                else settings.narration_polish_target_wpm
            ),
        ),
        cefr_level=(
            str(
                cefr_level
                if cefr_level is not None
                else settings.narration_polish_cefr_level
            ).strip().upper()
            or "B1"
        ),
        strength=(
            str(
                strength
                if strength is not None
                else settings.narration_polish_strength
            ).strip().lower()
            or "medium"
        ),
        safety_margin_sec=max(
            0.0,
            float(
                safety_margin_sec
                if safety_margin_sec is not None
                else settings.narration_polish_safety_margin_sec
            ),
        ),
        output_language=str(output_language or "en").strip() or "en",
    )


def build_narration_speech_options(
    settings: Settings,
    *,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
    pitch: str | None = None,
    boundary: str | None = None,
) -> NarrationSpeechOptions:
    resolved_model = str(settings.default_model_for_capability("tts")).strip()
    resolved_voice = (
        str(voice).strip()
        if voice is not None
        else settings.default_tts_voice()
    ) or settings.default_tts_voice()
    return NarrationSpeechOptions(
        voice=resolved_voice,
        model=resolved_model,
        rate=str(rate or settings.default_tts_rate()).strip() or settings.default_tts_rate(),
        volume=str(volume or settings.default_tts_volume()).strip()
        or settings.default_tts_volume(),
        pitch=str(pitch or settings.default_tts_pitch()).strip() or settings.default_tts_pitch(),
        boundary=str(boundary or settings.default_tts_boundary()).strip()
        or settings.default_tts_boundary(),
        ffmpeg_bin=settings.ffmpeg_path,
    )


def build_narration_video_options(
    settings: Settings,
    *,
    background_audio_volume: float | None = None,
    speech_audio_volume: float | None = None,
    ffmpeg_bin: str | None = None,
) -> NarrationVideoOptions:
    return NarrationVideoOptions(
        ffmpeg_bin=str(ffmpeg_bin or settings.ffmpeg_path).strip() or settings.ffmpeg_path,
        background_audio_volume=max(
            0.0,
            float(
                background_audio_volume
                if background_audio_volume is not None
                else settings.narration_video_background_audio_volume
            ),
        ),
        speech_audio_volume=max(
            0.0,
            float(
                speech_audio_volume
                if speech_audio_volume is not None
                else settings.narration_video_speech_audio_volume
            ),
        ),
    )


def build_subtitle_context_build_options(
    settings: Settings,
    *,
    chunk_cue_count: int | None = None,
    chunk_stride: int | None = None,
) -> SubtitleContextBuildOptions:
    return SubtitleContextBuildOptions(
        chunk_cue_count=max(
            1,
            int(
                chunk_cue_count
                if chunk_cue_count is not None
                else settings.subtitle_context_chunk_cue_count
            ),
        ),
        chunk_stride=max(
            1,
            int(
                chunk_stride
                if chunk_stride is not None
                else settings.subtitle_context_chunk_stride
            ),
        ),
    )


def build_subtitle_context_retrieve_options(
    settings: Settings,
    *,
    history_window_sec: float | None = None,
    top_k: int | None = None,
) -> SubtitleContextRetrieveOptions:
    return SubtitleContextRetrieveOptions(
        history_window_sec=float(
            history_window_sec
            if history_window_sec is not None
            else settings.subtitle_context_history_window_sec
        ),
        top_k=max(
            1,
            int(top_k if top_k is not None else settings.subtitle_context_top_k),
        ),
    )


def build_subtitle_extraction_options(
    settings: Settings,
    *,
    videocaptioner_bin: str | None = None,
    asr: str | None = None,
    language: str | None = None,
    timeout_sec: float | None = None,
) -> SubtitleExtractionOptions:
    resolved_timeout_sec = timeout_sec
    if resolved_timeout_sec is None and settings.videocaptioner_transcribe_timeout_ms is not None:
        resolved_timeout_sec = max(
            1.0, float(settings.videocaptioner_transcribe_timeout_ms) / 1000.0
        )
    return SubtitleExtractionOptions(
        videocaptioner_bin=_none_if_empty(
            videocaptioner_bin
            if videocaptioner_bin is not None
            else settings.videocaptioner_bin
        ),
        asr=str(asr or settings.videocaptioner_asr).strip().lower() or "bijian",
        language=str(language or settings.videocaptioner_language).strip() or "auto",
        timeout_sec=resolved_timeout_sec,
    )


def build_frame_pool_build_options(
    settings: Settings,
    *,
    ffmpeg_bin: str | None = None,
    max_edge_pixels: int | None = None,
    min_frames_per_shot: int | None = None,
    max_frames_per_shot: int | None = None,
    frames_per_shot_rate: float | None = None,
    dialogue_overlap_threshold: float | None = None,
    pyscenedetect_merge_sec: float | None = None,
) -> FramePoolBuildOptions:
    resolved_min_frames = max(
        1,
        int(
            min_frames_per_shot
            if min_frames_per_shot is not None
            else settings.pool_frames_per_shot_min
        ),
    )
    resolved_max_frames = max(
        resolved_min_frames,
        int(
            max_frames_per_shot
            if max_frames_per_shot is not None
            else settings.pool_frames_per_shot_max
        ),
    )
    return FramePoolBuildOptions(
        ffmpeg_bin=str(ffmpeg_bin or settings.ffmpeg_path).strip() or settings.ffmpeg_path,
        max_edge_pixels=max(
            16,
            int(
                max_edge_pixels
                if max_edge_pixels is not None
                else settings.narration_frame_max_edge
            ),
        ),
        min_frames_per_shot=resolved_min_frames,
        max_frames_per_shot=resolved_max_frames,
        frames_per_shot_rate=(
            float(frames_per_shot_rate)
            if frames_per_shot_rate is not None
            else (
                float(settings.pool_frames_per_shot_rate)
                if settings.pool_frames_per_shot_rate is not None
                else None
            )
        ),
        dialogue_overlap_threshold=max(
            0.0,
            float(
                dialogue_overlap_threshold
                if dialogue_overlap_threshold is not None
                else settings.dialogue_overlap_threshold
            ),
        ),
        pyscenedetect_merge_sec=max(
            0.0,
            float(
                pyscenedetect_merge_sec
                if pyscenedetect_merge_sec is not None
                else settings.pyscenedetect_merge_sec
            ),
        ),
    )
