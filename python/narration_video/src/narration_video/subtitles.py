from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pipeline_types import SubtitleCue
from subtitle_extraction import parse_srt_text

_PUNCT_SPLIT_RE = re.compile(r"(?<=[。！？!?；;：:,，])")


@dataclass(frozen=True)
class NarrationSubtitleBuildResult:
    source_srt_path: str
    speech_video_json_path: str
    output_srt_path: str
    inserted_cue_count: int
    total_cue_count: int


def build_subtitled_narration_srt(
    *,
    speech_video_json_path: str,
    source_srt_path: str,
    output_srt_path: str,
) -> NarrationSubtitleBuildResult:
    source_path = Path(source_srt_path)
    speech_path = Path(speech_video_json_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Subtitle file not found: {source_path}")
    if not speech_path.is_file():
        raise FileNotFoundError(f"Speech video JSON not found: {speech_path}")

    original_cues = parse_srt_text(source_path.read_text(encoding="utf-8"))
    payload = json.loads(speech_path.read_text(encoding="utf-8"))
    narration_cues = _build_narration_cues(payload)
    merged = _merge_cues(original_cues, narration_cues)

    output_path = Path(output_srt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_format_srt(merged), encoding="utf-8")

    return NarrationSubtitleBuildResult(
        source_srt_path=str(source_path),
        speech_video_json_path=str(speech_path),
        output_srt_path=str(output_path),
        inserted_cue_count=len(narration_cues),
        total_cue_count=len(merged),
    )


def _build_narration_cues(payload: dict[str, Any]) -> list[SubtitleCue]:
    segments = payload.get("narratedSegments")
    if not isinstance(segments, list):
        raise ValueError("speech video JSON has no narratedSegments list")
    cues: list[SubtitleCue] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        speech = seg.get("speech")
        if not isinstance(speech, dict):
            continue
        start_sec = float(seg["startSec"])
        audio_duration_sec = float(
            speech.get("audioDurationSec")
            or speech.get("targetDurationSec")
            or seg.get("durationSec")
            or max(0.0, float(seg["endSec"]) - start_sec)
        )
        text = str(speech.get("text") or seg.get("speechText") or seg.get("text") or "").strip()
        if not text or audio_duration_sec <= 0:
            continue
        cues.extend(_split_segment_into_cues(text=text, start_sec=start_sec, duration_sec=audio_duration_sec))
    return cues


def _split_segment_into_cues(*, text: str, start_sec: float, duration_sec: float) -> list[SubtitleCue]:
    parts = [part.strip() for part in _PUNCT_SPLIT_RE.split(text) if part and part.strip()]
    if not parts:
        return []
    weighted = [max(1, _visible_char_weight(part)) for part in parts]
    total_weight = sum(weighted)
    if total_weight <= 0:
        total_weight = len(parts)

    cues: list[SubtitleCue] = []
    cursor = float(start_sec)
    remaining_end = float(start_sec) + float(duration_sec)
    for idx, part in enumerate(parts):
        if idx == len(parts) - 1:
            end_sec = remaining_end
        else:
            share = duration_sec * (weighted[idx] / total_weight)
            end_sec = min(remaining_end, cursor + share)
        if end_sec <= cursor:
            end_sec = min(remaining_end, cursor + 0.05)
        cues.append(SubtitleCue(start_sec=cursor, end_sec=end_sec, text=part))
        cursor = end_sec
    if cues:
        last = cues[-1]
        cues[-1] = SubtitleCue(start_sec=last.start_sec, end_sec=remaining_end, text=last.text)
    return cues


def _visible_char_weight(text: str) -> int:
    compact = re.sub(r"\s+", "", text)
    return len(compact)


def _merge_cues(original: Iterable[SubtitleCue], inserted: Iterable[SubtitleCue]) -> list[SubtitleCue]:
    merged = list(original) + list(inserted)
    merged.sort(key=lambda cue: (cue.start_sec, cue.end_sec, cue.text))
    return merged


def _format_srt(cues: Iterable[SubtitleCue]) -> str:
    lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        lines.append(str(index))
        lines.append(f"{_format_ts(cue.start_sec)} --> {_format_ts(cue.end_sec)}")
        lines.append(cue.text.strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_ts(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000.0)))
    hh = millis // 3_600_000
    millis -= hh * 3_600_000
    mm = millis // 60_000
    millis -= mm * 60_000
    ss = millis // 1000
    ms = millis - ss * 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"
