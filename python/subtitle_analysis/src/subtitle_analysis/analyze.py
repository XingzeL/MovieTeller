from __future__ import annotations

import json
import subprocess
from pathlib import Path

from subtitle_extraction.parse_srt import parse_srt_text
from subtitle_extraction.types import SubtitleCue

from subtitle_analysis.types import NarrationCandidate, SubtitleAnalysisResult, TimeSpan


def probe_video_duration_sec(
    video_path: str,
    *,
    ffprobe_bin: str = "ffprobe",
    subprocess_run=subprocess.run,
) -> float:
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = subprocess_run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed ({proc.returncode}): {(proc.stderr or '').strip()}"
        )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError("ffprobe returned empty duration")
    return float(raw)


def _normalize_spans(cues: list[SubtitleCue]) -> list[tuple[float, float, str | None, str | None]]:
    if not cues:
        return []

    ordered = sorted(cues, key=lambda c: (c.start_sec, c.end_sec))
    merged: list[tuple[float, float, str | None, str | None]] = []
    cur_start = ordered[0].start_sec
    cur_end = ordered[0].end_sec
    cur_first_text = ordered[0].text
    cur_last_text = ordered[0].text

    for cue in ordered[1:]:
        if cue.start_sec <= cur_end:
            cur_end = max(cur_end, cue.end_sec)
            cur_last_text = cue.text
            continue
        merged.append((cur_start, cur_end, cur_first_text, cur_last_text))
        cur_start = cue.start_sec
        cur_end = cue.end_sec
        cur_first_text = cue.text
        cur_last_text = cue.text

    merged.append((cur_start, cur_end, cur_first_text, cur_last_text))
    return merged


def _candidate_from_gap(
    gap_start: float,
    gap_end: float,
    *,
    prev_text: str | None,
    next_text: str | None,
    prev_exists: bool,
    next_exists: bool,
    min_gap_sec: float,
    subtitle_guard_sec: float,
) -> NarrationCandidate | None:
    start = gap_start + (subtitle_guard_sec if prev_exists else 0.0)
    end = gap_end - (subtitle_guard_sec if next_exists else 0.0)
    if end <= start:
        return None
    if (end - start) < min_gap_sec:
        return None
    return NarrationCandidate(
        start_sec=start,
        end_sec=end,
        prev_subtitle_text=prev_text,
        next_subtitle_text=next_text,
    )


def analyze_subtitle_cues(
    cues: list[SubtitleCue],
    *,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
) -> SubtitleAnalysisResult:
    if min_gap_sec < 0:
        raise ValueError("min_gap_sec must be >= 0")
    if subtitle_guard_sec < 0:
        raise ValueError("subtitle_guard_sec must be >= 0")

    normalized = _normalize_spans(cues)
    subtitle_spans = tuple(TimeSpan(start, end) for start, end, _, _ in normalized)

    raw_gaps: list[TimeSpan] = []
    candidates: list[NarrationCandidate] = []

    if not normalized:
        if video_duration_sec is None:
            return SubtitleAnalysisResult(
                video_duration_sec=None,
                subtitle_spans=(),
                raw_gaps=(),
                narration_candidates=(),
            )
        full = TimeSpan(0.0, float(video_duration_sec))
        return SubtitleAnalysisResult(
            video_duration_sec=float(video_duration_sec),
            subtitle_spans=(),
            raw_gaps=(full,),
            narration_candidates=(
                NarrationCandidate(
                    start_sec=full.start_sec,
                    end_sec=full.end_sec,
                    prev_subtitle_text=None,
                    next_subtitle_text=None,
                ),
            )
            if full.duration_sec >= min_gap_sec
            else (),
        )

    first_start = normalized[0][0]
    if first_start > 0:
        gap = TimeSpan(0.0, first_start)
        raw_gaps.append(gap)
        cand = _candidate_from_gap(
            gap.start_sec,
            gap.end_sec,
            prev_text=None,
            next_text=normalized[0][2],
            prev_exists=False,
            next_exists=True,
            min_gap_sec=min_gap_sec,
            subtitle_guard_sec=subtitle_guard_sec,
        )
        if cand is not None:
            candidates.append(cand)

    for idx in range(len(normalized) - 1):
        cur_start, cur_end, _cur_first, cur_last = normalized[idx]
        nxt_start, nxt_end, nxt_first, _nxt_last = normalized[idx + 1]
        if nxt_start <= cur_end:
            continue
        gap = TimeSpan(cur_end, nxt_start)
        raw_gaps.append(gap)
        cand = _candidate_from_gap(
            gap.start_sec,
            gap.end_sec,
            prev_text=cur_last,
            next_text=nxt_first,
            prev_exists=True,
            next_exists=True,
            min_gap_sec=min_gap_sec,
            subtitle_guard_sec=subtitle_guard_sec,
        )
        if cand is not None:
            candidates.append(cand)

    if video_duration_sec is not None:
        last_end = normalized[-1][1]
        if video_duration_sec > last_end:
            gap = TimeSpan(last_end, float(video_duration_sec))
            raw_gaps.append(gap)
            cand = _candidate_from_gap(
                gap.start_sec,
                gap.end_sec,
                prev_text=normalized[-1][3],
                next_text=None,
                prev_exists=True,
                next_exists=False,
                min_gap_sec=min_gap_sec,
                subtitle_guard_sec=subtitle_guard_sec,
            )
            if cand is not None:
                candidates.append(cand)

    return SubtitleAnalysisResult(
        video_duration_sec=float(video_duration_sec)
        if video_duration_sec is not None
        else None,
        subtitle_spans=subtitle_spans,
        raw_gaps=tuple(raw_gaps),
        narration_candidates=tuple(candidates),
    )


def analyze_srt_text(
    srt_text: str,
    *,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
) -> SubtitleAnalysisResult:
    cues = parse_srt_text(srt_text)
    return analyze_subtitle_cues(
        cues,
        video_duration_sec=video_duration_sec,
        min_gap_sec=min_gap_sec,
        subtitle_guard_sec=subtitle_guard_sec,
    )


def analyze_subtitle_file(
    srt_path: str,
    *,
    video_path: str | None = None,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
    ffprobe_bin: str = "ffprobe",
) -> SubtitleAnalysisResult:
    path = Path(srt_path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    duration = video_duration_sec
    if duration is None and video_path is not None:
        duration = probe_video_duration_sec(video_path, ffprobe_bin=ffprobe_bin)
    return analyze_srt_text(
        raw,
        video_duration_sec=duration,
        min_gap_sec=min_gap_sec,
        subtitle_guard_sec=subtitle_guard_sec,
    )


def result_to_dict(result: SubtitleAnalysisResult) -> dict[str, object]:
    return {
        "videoDurationSec": result.video_duration_sec,
        "subtitleSpans": [
            {
                "startSec": span.start_sec,
                "endSec": span.end_sec,
                "durationSec": span.duration_sec,
            }
            for span in result.subtitle_spans
        ],
        "rawGaps": [
            {
                "startSec": gap.start_sec,
                "endSec": gap.end_sec,
                "durationSec": gap.duration_sec,
            }
            for gap in result.raw_gaps
        ],
        "narrationCandidates": [
            {
                "startSec": seg.start_sec,
                "endSec": seg.end_sec,
                "durationSec": seg.duration_sec,
                "prevSubtitleText": seg.prev_subtitle_text,
                "nextSubtitleText": seg.next_subtitle_text,
            }
            for seg in result.narration_candidates
        ],
    }


def result_to_json(result: SubtitleAnalysisResult) -> str:
    return json.dumps(result_to_dict(result), ensure_ascii=False)
