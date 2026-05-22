from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import (
    Settings,
    SubtitleContextRetrieveOptions,
    settings_from_dict,
)
from pipeline_types import NarrationCandidate, NarrationContext

from narration.narrate import narrate_segment_with_duration
from narration_polish import generate_vocab_study_card

from movie_pipeline.runtime_context import RunContext
from movie_pipeline.stage_executor import CapabilityLimiters, StageExecutor
from movie_pipeline.types import (
    NarrationPipelineConfig,
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


@dataclass(frozen=True)
class _CandidateWorkItem:
    index: int
    candidate: NarrationCandidate


@dataclass(frozen=True)
class _CandidateWorker:
    ctx: RunContext
    video_path: str
    subtitle_context_index_dir: str | None
    resolved_speech_output_dir: str | None
    frame_source_options: Any
    narrator: Callable[..., tuple[str, float]]
    polisher: Callable[..., object] | None
    synthesizer: Callable[..., object] | None
    limiters: CapabilityLimiters

    def run_candidate(self, item: _CandidateWorkItem) -> NarratedSegment:
        settings = self.ctx.settings
        pipeline_config = self.ctx.pipeline
        narration_options = pipeline_config.narration_options
        retrieve_options = pipeline_config.subtitle_context_retrieve_options
        polish_options = pipeline_config.polish_options
        speech_options = pipeline_config.speech_options
        polish_enabled = polish_options is not None
        speech_enabled = speech_options is not None
        seg = item.candidate
        timings: dict[str, Any] = {}
        with self.limiters.subtitle_context:
            retrieved_context_texts = _retrieve_context_texts_for_segment(
                subtitle_context_index_dir=self.subtitle_context_index_dir,
                segment_start_sec=seg.start_sec,
                query_text=seg.prev_subtitle_text,
                settings=settings,
                retrieve_options=retrieve_options,
            )
        narration_context = NarrationContext(
            segment_start_sec=seg.start_sec,
            segment_end_sec=seg.end_sec,
            prev_subtitle_text=seg.prev_subtitle_text,
            next_subtitle_text=seg.next_subtitle_text,
            retrieved_context_texts=retrieved_context_texts,
        )
        with self.limiters.narration:
            text, _duration = self.narrator(
                self.video_path,
                seg.start_sec,
                seg.end_sec,
                options=narration_options,
                frame_source_options=self.frame_source_options,
                settings=settings,
                timings_out=timings,
                narration_context=narration_context,
            )
        polish_details: NarrationPolishDetails | None = None
        speech_details: NarrationSpeechDetails | None = None
        vocab_study_card: dict[str, Any] | None = None
        speech_text = text
        if polish_enabled:
            if self.polisher is None:
                raise RuntimeError("Narration polisher is not available")
            with self.limiters.polish:
                polished = self.polisher(
                    text,
                    seg.duration_sec,
                    options=polish_options,
                    settings=settings,
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
                scene_title_zh=(
                    None
                    if getattr(polished, "scene_title_zh", None) is None
                    else (
                        s
                        if (s := str(getattr(polished, "scene_title_zh")).strip())
                        else None
                    )
                ),
            )
            with self.limiters.study_enrichment:
                raw_vocab, _vocab_timing_sec = generate_vocab_study_card(
                    text,
                    cefr_level=polish_details.cefr_level,
                    settings=settings,
                )
            vocab_study_card = raw_vocab if isinstance(raw_vocab, dict) else None
        if speech_enabled:
            if self.synthesizer is None:
                raise RuntimeError("Narration speech synthesizer is not available")
            if not self.resolved_speech_output_dir:
                raise ValueError(
                    "resolved_speech_output_dir is required when speech synthesis is enabled"
                )
            speech_dir = Path(self.resolved_speech_output_dir)
            filename = (
                f"segment_{item.index:03d}_"
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
            with self.limiters.tts:
                spoken = self.synthesizer(
                    speech_text,
                    seg.duration_sec,
                    output_path=str(audio_path),
                    metadata_path=str(metadata_path),
                    target_duration_sec=target_duration_sec,
                    options=speech_options,
                    settings=settings,
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
        return NarratedSegment(
            start_sec=seg.start_sec,
            end_sec=seg.end_sec,
            narration_text=text,
            prev_subtitle_text=seg.prev_subtitle_text,
            next_subtitle_text=seg.next_subtitle_text,
            speech_text=speech_text,
            polish=polish_details,
            speech=speech_details,
            vocab_study_card=vocab_study_card,
            timing_extract_sec=(
                float(timings["extract_sec"]) if "extract_sec" in timings else None
            ),
            timing_api_sec=float(timings["api_sec"]) if "api_sec" in timings else None,
            timing_total_sec=(
                float(timings["total_sec"]) if "total_sec" in timings else None
            ),
            frame_count=int(timings["frame_count"])
            if "frame_count" in timings
            else None,
        )


def _group_candidate_work(
    candidates: tuple[NarrationCandidate, ...],
    *,
    group_size: int,
) -> tuple[tuple[_CandidateWorkItem, ...], ...]:
    size = max(1, int(group_size))
    items = tuple(
        _CandidateWorkItem(index=index, candidate=candidate)
        for index, candidate in enumerate(candidates, start=1)
    )
    return tuple(items[index : index + size] for index in range(0, len(items), size))


def _run_candidate_group(
    group: tuple[_CandidateWorkItem, ...],
    *,
    worker: _CandidateWorker,
) -> tuple[NarratedSegment, ...]:
    out: list[NarratedSegment] = []
    for item in group:
        try:
            out.append(worker.run_candidate(item))
        except Exception as exc:
            raise RuntimeError(f"segment {item.index} failed") from exc
    return tuple(out)


def narrate_analysis_candidates(
    analysis: SubtitleAnalysisResult,
    *,
    ctx: RunContext,
    video_path: str,
    subtitle_context_index_dir: str | None = None,
    resolved_speech_output_dir: str | None = None,
    frame_source_options: FrameSourceOptions | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
) -> tuple[NarratedSegment, ...]:
    """Narrate all analysis candidates using a single :class:`RunContext` (no separate settings/options)."""
    settings = ctx.settings
    pipeline_config = ctx.pipeline
    polish_options = pipeline_config.polish_options
    call_narrator = narrator or narrate_segment_with_duration
    polish_enabled = polish_options is not None
    call_polisher: Callable[..., object] | None = polisher
    if polish_enabled and call_polisher is None:
        from narration_polish import polish_narration_text as _default_polisher

        call_polisher = _default_polisher
    speech_enabled = pipeline_config.speech_options is not None
    call_synthesizer: Callable[..., object] | None = synthesizer
    if speech_enabled and call_synthesizer is None:
        from narration_speech import synthesize_narration_text as _default_synthesizer

        call_synthesizer = _default_synthesizer
    resolved_frame = (
        frame_source_options
        or pipeline_config.frame_source_options
    )
    if resolved_frame is None:
        raise ValueError(
            "frame_source_options is required on NarrationPipelineConfig or pass frame_source_options=..."
        )
    speech_dir = Path(resolved_speech_output_dir) if resolved_speech_output_dir else None
    if speech_dir is not None:
        speech_dir.mkdir(parents=True, exist_ok=True)

    candidates = analysis.narration_candidates
    if not candidates:
        return ()

    parallelism = settings.workflow_parallelism_options()
    groups = _group_candidate_work(
        candidates,
        group_size=parallelism.segment_group_size,
    )
    worker = _CandidateWorker(
        ctx=ctx,
        video_path=video_path,
        subtitle_context_index_dir=subtitle_context_index_dir,
        resolved_speech_output_dir=resolved_speech_output_dir,
        frame_source_options=resolved_frame,
        narrator=call_narrator,
        polisher=call_polisher,
        synthesizer=call_synthesizer,
        limiters=CapabilityLimiters.from_options(settings.capability_concurrency_options()),
    )
    group_results = StageExecutor().map_ordered(
        groups,
        lambda group: _run_candidate_group(group, worker=worker),
        concurrency=parallelism.segment_group_concurrency,
        stage_name="narration_group",
    )
    return tuple(segment for group in group_results for segment in group)


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
            "studyCard": (
                {"vocab": seg.vocab_study_card}
                if seg.vocab_study_card is not None
                else None
            ),
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
                    "sceneTitleZh": seg.polish.scene_title_zh,
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


def run_pipeline_ctx(
    *,
    srt_path: str,
    video_path: str,
    ctx: RunContext,
    subtitle_context_index_dir: str | None = None,
    build_subtitle_context: bool = False,
    speech_output_dir: str | None = None,
    narrator: Callable[..., tuple[str, float]] | None = None,
    polisher: Callable[..., object] | None = None,
    synthesizer: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Run the text/speech narration pipeline using a single :class:`RunContext`."""
    pipeline_config = ctx.pipeline
    resolved_settings = ctx.settings
    analysis = analyze_subtitle_file(
        srt_path,
        video_path=video_path,
        video_duration_sec=pipeline_config.video_duration_sec,
        min_gap_sec=pipeline_config.min_gap_sec,
        subtitle_guard_sec=pipeline_config.subtitle_guard_sec,
        ffprobe_bin=pipeline_config.ffprobe_bin,
    )
    resolved_subtitle_context_index_dir = _resolve_subtitle_context_index_dir(
        srt_path,
        subtitle_context_index_dir,
    )
    if build_subtitle_context:
        from subtitle_context import build_subtitle_context_index

        resolved_subtitle_context_index_dir = (
            resolved_subtitle_context_index_dir
            or str(Path(srt_path).with_suffix("")) + ".subtitle_context"
        )
        build_subtitle_context_index(
            srt_path=srt_path,
            output_dir=resolved_subtitle_context_index_dir,
            options=pipeline_config.subtitle_context_build_options,
            settings=resolved_settings,
        )

    speech_requested = pipeline_config.speech_options is not None
    resolved_speech_output_dir = (speech_output_dir or "").strip() or None
    if speech_requested:
        if not resolved_speech_output_dir:
            raise ValueError(
                "speech_output_dir is required when speech_options is set"
            )

    resolved_frame_source_options = pipeline_config.frame_source_options
    if resolved_frame_source_options is None:
        raise ValueError(
            "frame_source_options is required on NarrationPipelineConfig for run_pipeline_ctx"
        )
    narrated_segments = narrate_analysis_candidates(
        analysis,
        ctx=ctx,
        video_path=video_path,
        subtitle_context_index_dir=resolved_subtitle_context_index_dir,
        resolved_speech_output_dir=resolved_speech_output_dir,
        frame_source_options=resolved_frame_source_options,
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
    return payload
