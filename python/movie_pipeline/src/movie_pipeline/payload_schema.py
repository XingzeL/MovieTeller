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


class NarratedSegmentPayload(TypedDict, total=False):
    startSec: float
    endSec: float
    durationSec: float
    text: str
    speechText: str
    prevSubtitleText: str | None
    nextSubtitleText: str | None
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
    """Validate minimal keys for a text-stage pipeline JSON dict."""
    segs = _require_narrated_segments(data, kind="text")
    for i, seg in enumerate(segs):
        for key in ("startSec", "endSec", "text"):
            if key not in seg:
                raise ValueError(f"narratedSegments[{i}] missing required key {key!r}")
    if "renderedVideo" in data:
        raise ValueError("text payload must not contain renderedVideo")
    return data  # type: ignore[return-value]


def parse_rendered_video_dict(data: dict[str, Any] | None) -> RenderedVideoPayload | None:
    if data is None:
        return None
    for key in ("videoPath", "outputPath"):
        if key not in data:
            raise ValueError(f"renderedVideo missing required key {key!r}")
    return data  # type: ignore[return-value]


def parse_pipeline_speech_dict(data: dict[str, Any]) -> PipelineSpeechPayload:
    segs = _require_narrated_segments(data, kind="speech")
    if "renderedVideo" in data:
        raise ValueError("speech payload must not contain renderedVideo")
    for i, seg in enumerate(segs):
        sp = seg.get("speech")
        if not isinstance(sp, dict):
            raise ValueError(f"narratedSegments[{i}] missing speech object")
        if not str(sp.get("audioPath") or "").strip():
            raise ValueError(f"narratedSegments[{i}].speech missing audioPath")
    return data  # type: ignore[return-value]


def parse_pipeline_render_dict(data: dict[str, Any]) -> PipelineRenderPayload:
    _require_narrated_segments(data, kind="render")
    inner = data.get("renderedVideo")
    if not isinstance(inner, dict):
        raise ValueError("render payload requires renderedVideo object")
    parse_rendered_video_dict(inner)
    return data  # type: ignore[return-value]


def parse_pipeline_text_json_path(path: str | Path) -> PipelineTextPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return parse_pipeline_text_dict(raw)


def parse_pipeline_speech_json_path(path: str | Path) -> PipelineSpeechPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return parse_pipeline_speech_dict(raw)


def parse_pipeline_render_json_path(path: str | Path) -> PipelineRenderPayload:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pipeline JSON root must be an object")
    return parse_pipeline_render_dict(raw)


def serialize_pipeline_text_payload(payload: PipelineTextPayload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def serialize_pipeline_speech_payload(payload: PipelineSpeechPayload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def serialize_pipeline_render_payload(payload: PipelineRenderPayload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
