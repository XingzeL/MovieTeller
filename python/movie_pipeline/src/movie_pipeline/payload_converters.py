"""Runtime narration objects → JSON-safe payload dicts.

Kept separate from :mod:`movie_pipeline.payload_schema` so schema/validation
stays focused on TypedDict contracts and parsing.
"""

from __future__ import annotations

from typing import Any

from movie_pipeline.payload_schema import (
    NarratedSegmentPayload,
    NarratedSegmentPolishPayload,
    NarratedSegmentSpeechPayload,
    RenderedVideoPayload,
    parse_rendered_video_dict,
    validate_narrated_segment_dict,
)


def polish_details_to_payload(polish: Any | None) -> NarratedSegmentPolishPayload | None:
    if polish is None:
        return None
    payload: NarratedSegmentPolishPayload = {
        "text": str(polish.text),
        "segmentDurationSec": float(polish.segment_duration_sec),
        "targetDurationSec": float(polish.target_duration_sec),
        "safetyMarginSec": float(polish.safety_margin_sec),
        "speakingRateWpm": int(polish.speaking_rate_wpm),
        "targetWordCount": int(polish.target_word_count),
        "originalWordCount": int(polish.original_word_count),
        "polishedWordCount": int(polish.polished_word_count),
        "estimatedOriginalDurationSec": float(polish.estimated_original_duration_sec),
        "estimatedPolishedDurationSec": float(polish.estimated_polished_duration_sec),
        "cefrLevel": str(polish.cefr_level),
        "strength": str(polish.strength),
        "provider": str(polish.provider),
        "model": str(polish.model),
        "fitsDuration": bool(polish.fits_duration),
        "timingApiSec": polish.timing_api_sec,
        "sceneTitleZh": polish.scene_title_zh,
    }
    return payload


def speech_details_to_payload(speech: Any | None) -> NarratedSegmentSpeechPayload | None:
    if speech is None:
        return None
    payload: NarratedSegmentSpeechPayload = {
        "text": str(speech.text),
        "audioPath": str(speech.audio_path),
        "metadataPath": speech.metadata_path,
        "segmentDurationSec": float(speech.segment_duration_sec),
        "targetDurationSec": float(speech.target_duration_sec),
        "rawDurationSec": float(speech.raw_duration_sec),
        "audioDurationSec": float(speech.audio_duration_sec),
        "durationDeltaSec": float(speech.duration_delta_sec),
        "provider": str(speech.provider),
        "voice": str(speech.voice),
        "rate": str(speech.rate),
        "volume": str(speech.volume),
        "pitch": str(speech.pitch),
        "boundary": str(speech.boundary),
        "fitApplied": bool(speech.fit_applied),
        "fitsDuration": bool(speech.fits_duration),
        "timingTtsSec": speech.timing_tts_sec,
        "timingFitSec": speech.timing_fit_sec,
    }
    return payload


def rendered_video_to_payload(rendered: Any) -> RenderedVideoPayload:
    payload: RenderedVideoPayload = {
        "videoPath": str(rendered.video_path),
        "outputPath": str(rendered.output_path),
        "segmentCount": int(rendered.segment_count),
        "videoDurationSec": float(rendered.video_duration_sec),
        "backgroundAudioVolume": float(rendered.background_audio_volume),
        "speechAudioVolume": float(rendered.speech_audio_volume),
        "subtitleSrtPath": rendered.subtitle_srt_path,
        "timingRenderSec": (
            float(rendered.timing_render_sec)
            if rendered.timing_render_sec is not None
            else None
        ),
    }
    parse_rendered_video_dict(dict(payload))
    return payload


def narrated_segment_to_payload(segment: Any) -> NarratedSegmentPayload:
    payload: NarratedSegmentPayload = {
        "startSec": float(segment.start_sec),
        "endSec": float(segment.end_sec),
        "durationSec": float(segment.duration_sec),
        "text": str(segment.narration_text),
        "speechText": str(segment.final_text),
        "prevSubtitleText": segment.prev_subtitle_text,
        "nextSubtitleText": segment.next_subtitle_text,
        "studyCard": (
            {"vocab": segment.vocab_study_card}
            if segment.vocab_study_card is not None
            else None
        ),
        "polish": polish_details_to_payload(segment.polish),
        "speech": speech_details_to_payload(segment.speech),
        "timingExtractSec": segment.timing_extract_sec,
        "timingApiSec": segment.timing_api_sec,
        "timingTotalSec": segment.timing_total_sec,
        "frameCount": segment.frame_count,
    }
    validate_narrated_segment_dict(dict(payload), index=0)
    return payload
