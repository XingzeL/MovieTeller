from __future__ import annotations

import re
from typing import List

from pipeline_types import SubtitleCue

_TS_LINE = re.compile(
    r"^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
)


def _timestamp_to_sec(ts: str) -> float:
    ts = ts.strip()
    hh, mm, rest = ts.split(":")
    sec, ms = rest.split(",")
    return int(hh) * 3600 + int(mm) * 60 + int(sec) + int(ms) / 1000.0


def parse_srt_text(content: str) -> List[SubtitleCue]:
    """
    Parse SubRip (.srt) text into cues.

    Handles UTF-8 BOM, CRLF, multi-line subtitle text (joined with single space).
    Skips malformed blocks when possible.
    """
    if not content:
        return []
    text = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n+", text.strip())
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip() != ""]
        if len(lines) < 2:
            continue
        idx = 0
        if lines[0].isdigit():
            idx = 1
        if idx >= len(lines):
            continue
        m = _TS_LINE.match(lines[idx])
        if not m:
            continue
        start_raw, end_raw = m.group(1), m.group(2)
        body_lines = lines[idx + 1 :]
        if not body_lines:
            continue
        body = " ".join(body_lines)
        try:
            start_sec = _timestamp_to_sec(start_raw)
            end_sec = _timestamp_to_sec(end_raw)
        except ValueError:
            continue
        if end_sec <= start_sec:
            continue
        cues.append(SubtitleCue(start_sec=start_sec, end_sec=end_sec, text=body))
    return cues
