"""Typed shapes for pipeline JSON payloads (IDE + refactor safety).

Runtime values are plain ``dict``; :class:`typing.TypedDict` documents contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class NarratedSegmentPolishPayload(TypedDict, total=False):
    text: str
    segmentDurationSec: float
    targetDurationSec: float
    safetyMarginSec: float
    speakingRateWpm: int
    targetWordCount: int
    originalWordCount: int
    polishedWordCount: int
    estimatedOriginalDurationSec: float
    estimatedPolishedDurationSec: float
    cefrLevel: str
    strength: str
    provider: str
    model: str
    fitsDuration: bool
    timingApiSec: float | None
    sceneTitleZh: str | None


class NarratedSegmentStudyCardPayload(TypedDict, total=False):
    vocab: dict[str, Any]


class NarratedSegmentSpeechPayload(TypedDict, total=False):
    text: str
    audioPath: str
    metadataPath: str
    segmentDurationSec: float
    targetDurationSec: float
    rawDurationSec: float
    audioDurationSec: float
    durationDeltaSec: float
    provider: str
    voice: str
    rate: str
    volume: str
    pitch: str
    boundary: str
    fitApplied: bool
    fitsDuration: bool
    timingTtsSec: float | None
    timingFitSec: float | None


class RenderedVideoPayload(TypedDict, total=False):
    """Mux / embed stage output (was an untyped ``dict`` on the text payload)."""

    videoPath: str
    outputPath: str
    segmentCount: int
    videoDurationSec: float
    backgroundAudioVolume: float
    speechAudioVolume: float
    subtitleSrtPath: str | None
    timingRenderSec: float | None


class SubtitleMergePayload(TypedDict, total=False):
    sourceSrtPath: str
    speechVideoJsonPath: str
    outputSrtPath: str
    insertedCueCount: int
    totalCueCount: int


class NarratedSegmentPayload(TypedDict, total=False):
    startSec: float
    endSec: float
    durationSec: float
    text: str
    speechText: str
    prevSubtitleText: str | None
    nextSubtitleText: str | None
    studyCard: NarratedSegmentStudyCardPayload | None
    polish: NarratedSegmentPolishPayload | None
    speech: NarratedSegmentSpeechPayload | None
    timingExtractSec: float | None
    timingApiSec: float | None
    timingTotalSec: float | None
    frameCount: int | None


class PipelineTextPayload(TypedDict, total=False):
    """Shape produced by :func:`movie_pipeline.pipeline.run_pipeline_ctx` (text path)."""

    videoDurationSec: float
    subtitleSpans: list[dict[str, Any]]
    rawGaps: list[dict[str, Any]]
    narrationCandidates: list[dict[str, Any]]
    narratedSegments: list[NarratedSegmentPayload]
    speechOutputDir: str | None
    subtitleContextIndexDir: str | None


class PipelineSpeechPayload(TypedDict, total=False):
    """Speech-stage payload: text payload plus synthesized ``speech`` blocks."""

    videoDurationSec: float
    subtitleSpans: list[dict[str, Any]]
    rawGaps: list[dict[str, Any]]
    narrationCandidates: list[dict[str, Any]]
    speechOutputDir: str | None
    subtitleContextIndexDir: str | None
    narratedSegments: list[NarratedSegmentPayload]


class PipelineRenderPayload(TypedDict, total=False):
    """Render-stage payload: prior payload plus packaged video metadata."""

    videoDurationSec: float
    subtitleSpans: list[dict[str, Any]]
    rawGaps: list[dict[str, Any]]
    narrationCandidates: list[dict[str, Any]]
    speechOutputDir: str | None
    subtitleContextIndexDir: str | None
    narratedSegments: list[NarratedSegmentPayload]
    renderedVideo: RenderedVideoPayload


class WorkflowArtifactsPayload(TypedDict, total=False):
    videoPath: str
    srtPath: str
    framePoolManifest: str | None
    subtitleContextIndexDir: str | None
    outputRoot: str
    textJsonPath: str | None
    speechJsonPath: str | None
    renderJsonPath: str | None
    finalSrtPath: str | None
    studyCardsHtmlPath: str | None
    studyCardsHtmlError: str | None
    artifactManifestPath: str | None


class WorkflowPayload(TypedDict, total=False):
    """Full workflow output: one pipeline payload plus workflow-level artifacts."""

    videoDurationSec: float
    subtitleSpans: list[dict[str, Any]]
    rawGaps: list[dict[str, Any]]
    narrationCandidates: list[dict[str, Any]]
    speechOutputDir: str | None
    subtitleContextIndexDir: str | None
    narratedSegments: list[NarratedSegmentPayload]
    renderedVideo: RenderedVideoPayload
    subtitleMerge: SubtitleMergePayload
    workflowArtifacts: WorkflowArtifactsPayload


_TEXT_TOP_LEVEL_KEYS = frozenset(
    {
        "videoDurationSec",
        "subtitleSpans",
        "rawGaps",
        "narrationCandidates",
        "narratedSegments",
        "speechOutputDir",
        "subtitleContextIndexDir",
    }
)

_RENDER_TOP_LEVEL_KEYS = _TEXT_TOP_LEVEL_KEYS | {"renderedVideo"}

_WORKFLOW_TOP_LEVEL_KEYS = _RENDER_TOP_LEVEL_KEYS | {"subtitleMerge", "workflowArtifacts"}

_SEGMENT_KEYS = frozenset(
    {
        "startSec",
        "endSec",
        "durationSec",
        "text",
        "speechText",
        "prevSubtitleText",
        "nextSubtitleText",
        "studyCard",
        "polish",
        "speech",
        "timingExtractSec",
        "timingApiSec",
        "timingTotalSec",
        "frameCount",
    }
)

_POLISH_KEYS = frozenset(NarratedSegmentPolishPayload.__annotations__)
_SPEECH_KEYS = frozenset(NarratedSegmentSpeechPayload.__annotations__)
_RENDERED_VIDEO_KEYS = frozenset(RenderedVideoPayload.__annotations__)
_SUBTITLE_MERGE_KEYS = frozenset(SubtitleMergePayload.__annotations__)
_WORKFLOW_ARTIFACTS_KEYS = frozenset(WorkflowArtifactsPayload.__annotations__)


def _reject_unknown_keys(
    obj: dict[str, Any],
    *,
    allowed: frozenset[str],
    path: str,
) -> None:
    extra = sorted(set(obj) - allowed)
    if extra:
        raise ValueError(f"{path} contains unexpected keys: {', '.join(extra)}")


def _require_keys(obj: dict[str, Any], *, keys: tuple[str, ...], path: str) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"{path} missing required key {key!r}")


def _validate_segment_shape(seg: dict[str, Any], *, index: int) -> None:
    path = f"narratedSegments[{index}]"
    _reject_unknown_keys(seg, allowed=_SEGMENT_KEYS, path=path)
    _require_keys(
        seg,
        keys=("startSec", "endSec", "durationSec", "text", "speechText"),
        path=path,
    )
    if not str(seg.get("text") or "").strip():
        raise ValueError(f"{path}.text must be non-empty")
    polish = seg.get("polish")
    if polish is not None:
        if not isinstance(polish, dict):
            raise ValueError(f"{path}.polish must be an object or null")
        _reject_unknown_keys(polish, allowed=_POLISH_KEYS, path=f"{path}.polish")
    speech = seg.get("speech")
    if speech is not None:
        if not isinstance(speech, dict):
            raise ValueError(f"{path}.speech must be an object or null")
        _reject_unknown_keys(speech, allowed=_SPEECH_KEYS, path=f"{path}.speech")


def _validate_pipeline_common(data: dict[str, Any], *, kind: str) -> list[dict[str, Any]]:
    _require_keys(data, keys=("narratedSegments",), path=f"{kind} payload")
    segs = _require_narrated_segments(data, kind=kind)
    for i, seg in enumerate(segs):
        _validate_segment_shape(seg, index=i)
    return segs


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
    _validate_segment_shape(dict(payload), index=0)
    return payload


def validate_workflow_artifacts_dict(data: dict[str, Any] | None) -> WorkflowArtifactsPayload | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("workflowArtifacts must be an object")
    _reject_unknown_keys(data, allowed=_WORKFLOW_ARTIFACTS_KEYS, path="workflowArtifacts")
    _require_keys(
        data,
        keys=("videoPath", "srtPath", "framePoolManifest", "subtitleContextIndexDir", "outputRoot"),
        path="workflowArtifacts",
    )
    return data  # type: ignore[return-value]


def validate_subtitle_merge_dict(data: dict[str, Any] | None) -> SubtitleMergePayload | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("subtitleMerge must be an object")
    _reject_unknown_keys(data, allowed=_SUBTITLE_MERGE_KEYS, path="subtitleMerge")
    _require_keys(
        data,
        keys=(
            "sourceSrtPath",
            "speechVideoJsonPath",
            "outputSrtPath",
            "insertedCueCount",
            "totalCueCount",
        ),
        path="subtitleMerge",
    )
    return data  # type: ignore[return-value]


def _require_narrated_segments(data: dict[str, Any], *, kind: str) -> list[dict[str, Any]]:
    segs = data.get("narratedSegments")
    if not isinstance(segs, list) or not segs:
        raise ValueError(f"{kind} payload missing non-empty narratedSegments list")
    normalized: list[dict[str, Any]] = []
    for i, seg in enumerate(segs):
        if not isinstance(seg, dict):
            raise ValueError(f"narratedSegments[{i}] must be an object")
        normalized.append(seg)
    return normalized


def parse_pipeline_text_dict(data: dict[str, Any]) -> PipelineTextPayload:
    """Validate the text-stage pipeline JSON contract."""
    _reject_unknown_keys(data, allowed=_TEXT_TOP_LEVEL_KEYS, path="text payload")
    _validate_pipeline_common(data, kind="text")
    return data  # type: ignore[return-value]


def pipeline_text_payload_from_dict(data: dict[str, Any]) -> PipelineTextPayload:
    """Return the text-stage subset from a pipeline or workflow payload."""
    if not isinstance(data, dict):
        raise ValueError("pipeline payload must be an object")
    text_part = {k: v for k, v in data.items() if k in _TEXT_TOP_LEVEL_KEYS}
    return parse_pipeline_text_dict(text_part)


def pipeline_speech_payload_from_dict(data: dict[str, Any]) -> PipelineSpeechPayload:
    """Return the speech-stage subset from a pipeline or workflow payload."""
    if not isinstance(data, dict):
        raise ValueError("pipeline payload must be an object")
    speech_part = {k: v for k, v in data.items() if k in _TEXT_TOP_LEVEL_KEYS}
    return parse_pipeline_speech_dict(speech_part)


def pipeline_render_payload_from_dict(data: dict[str, Any]) -> PipelineRenderPayload:
    """Return the render-stage subset from a pipeline or workflow payload."""
    if not isinstance(data, dict):
        raise ValueError("pipeline payload must be an object")
    render_part = {k: v for k, v in data.items() if k in _RENDER_TOP_LEVEL_KEYS}
    return parse_pipeline_render_dict(render_part)


def parse_rendered_video_dict(data: dict[str, Any] | None) -> RenderedVideoPayload | None:
    if data is None:
        return None
    _reject_unknown_keys(data, allowed=_RENDERED_VIDEO_KEYS, path="renderedVideo")
    _require_keys(data, keys=("videoPath", "outputPath"), path="renderedVideo")
    return data  # type: ignore[return-value]


def parse_pipeline_speech_dict(data: dict[str, Any]) -> PipelineSpeechPayload:
    _reject_unknown_keys(data, allowed=_TEXT_TOP_LEVEL_KEYS, path="speech payload")
    segs = _validate_pipeline_common(data, kind="speech")
    for i, seg in enumerate(segs):
        sp = seg.get("speech")
        if not isinstance(sp, dict):
            raise ValueError(f"narratedSegments[{i}] missing speech object")
        if not str(sp.get("audioPath") or "").strip():
            raise ValueError(f"narratedSegments[{i}].speech missing audioPath")
    return data  # type: ignore[return-value]


def parse_pipeline_render_dict(data: dict[str, Any]) -> PipelineRenderPayload:
    _reject_unknown_keys(data, allowed=_RENDER_TOP_LEVEL_KEYS, path="render payload")
    _validate_pipeline_common(data, kind="render")
    inner = data.get("renderedVideo")
    if not isinstance(inner, dict):
        raise ValueError("render payload requires renderedVideo object")
    parse_rendered_video_dict(inner)
    return data  # type: ignore[return-value]


def parse_workflow_payload_dict(data: dict[str, Any]) -> WorkflowPayload:
    """Validate full workflow output with workflowArtifacts attached."""
    _reject_unknown_keys(data, allowed=_WORKFLOW_TOP_LEVEL_KEYS, path="workflow payload")
    artifacts = data.get("workflowArtifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("workflow payload requires workflowArtifacts object")
    validate_workflow_artifacts_dict(artifacts)
    merge_payload = data.get("subtitleMerge")
    if merge_payload is not None:
        validate_subtitle_merge_dict(merge_payload)

    pipeline_part = {
        k: v for k, v in data.items() if k not in {"workflowArtifacts", "subtitleMerge"}
    }
    if "renderedVideo" in pipeline_part:
        parse_pipeline_render_dict(pipeline_part)
    elif any(
        isinstance(seg, dict) and isinstance(seg.get("speech"), dict)
        for seg in pipeline_part.get("narratedSegments") or []
    ):
        parse_pipeline_speech_dict(pipeline_part)
    else:
        parse_pipeline_text_dict(pipeline_part)
    return data  # type: ignore[return-value]


def parse_pipeline_text_json_path(path: str | Path) -> PipelineTextPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return pipeline_text_payload_from_dict(raw)


def parse_pipeline_speech_json_path(path: str | Path) -> PipelineSpeechPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return pipeline_speech_payload_from_dict(raw)


def parse_pipeline_render_json_path(path: str | Path) -> PipelineRenderPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return pipeline_render_payload_from_dict(raw)


def parse_workflow_payload_json_path(path: str | Path) -> WorkflowPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("workflow JSON root must be an object")
    return parse_workflow_payload_dict(raw)


def serialize_pipeline_text_payload(payload: PipelineTextPayload) -> str:
    return json.dumps(pipeline_text_payload_from_dict(dict(payload)), ensure_ascii=False, indent=2)


def serialize_pipeline_speech_payload(payload: PipelineSpeechPayload) -> str:
    return json.dumps(pipeline_speech_payload_from_dict(dict(payload)), ensure_ascii=False, indent=2)


def serialize_pipeline_render_payload(payload: PipelineRenderPayload) -> str:
    return json.dumps(pipeline_render_payload_from_dict(dict(payload)), ensure_ascii=False, indent=2)


def serialize_workflow_payload(payload: WorkflowPayload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
