from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable


def ffprobe_path_for(ffmpeg_bin: str) -> str:
    """Best-effort sibling ffprobe next to ffmpeg."""
    p = Path(ffmpeg_bin)
    if p.name == "ffmpeg":
        return str(p.with_name("ffprobe"))
    return "ffprobe"


def probe_duration_sec(
    media_path: str,
    *,
    ffprobe_bin: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> float:
    """Return container duration in seconds (float)."""
    path = Path(media_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {media_path}")
    proc = subprocess_run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed ({proc.returncode}): {(proc.stderr or proc.stdout).strip()}"
        )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError("ffprobe returned empty duration")
    return float(raw)


def segment_duration_sec(
    media_path: str,
    start_sec: float | None,
    end_sec: float | None,
    *,
    ffprobe_bin: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> float:
    """
    Duration of the requested segment in seconds.
    If both start and end are None, uses full file duration.
    """
    if (start_sec is None) ^ (end_sec is None):
        raise ValueError("start_sec and end_sec must both be set or both be None")
    if start_sec is None and end_sec is None:
        return probe_duration_sec(
            media_path,
            ffprobe_bin=ffprobe_bin,
            subprocess_run=subprocess_run,
        )
    assert start_sec is not None and end_sec is not None
    if end_sec <= start_sec:
        raise ValueError(f"end_sec must be > start_sec, got {start_sec=} {end_sec=}")
    return end_sec - start_sec
