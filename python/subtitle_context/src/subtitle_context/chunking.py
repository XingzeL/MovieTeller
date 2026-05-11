from __future__ import annotations

from subtitle_extraction.types import SubtitleCue

from subtitle_context.types import SubtitleContextChunk


def _valid_cues(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    return sorted(
        [
            cue
            for cue in cues
            if cue.end_sec > cue.start_sec and str(cue.text or "").strip()
        ],
        key=lambda cue: (cue.start_sec, cue.end_sec),
    )


def chunk_subtitle_cues(
    cues: list[SubtitleCue],
    *,
    cue_count: int,
    stride: int,
) -> tuple[SubtitleContextChunk, ...]:
    window = max(1, int(cue_count))
    step = max(1, int(stride))
    ordered = _valid_cues(cues)
    if not ordered:
        return ()

    out: list[SubtitleContextChunk] = []
    seen_ranges: set[tuple[float, float]] = set()
    for start_idx in range(0, len(ordered), step):
        subset = ordered[start_idx : start_idx + window]
        if not subset:
            break
        start_sec = float(subset[0].start_sec)
        end_sec = float(subset[-1].end_sec)
        key = (start_sec, end_sec)
        if key in seen_ranges:
            continue
        seen_ranges.add(key)
        text = " ".join(str(cue.text).strip() for cue in subset if str(cue.text).strip())
        out.append(
            SubtitleContextChunk(
                chunk_id=f"{len(out) + 1:06d}",
                start_sec=start_sec,
                end_sec=end_sec,
                text=text,
                cue_count=len(subset),
            )
        )
    return tuple(out)
