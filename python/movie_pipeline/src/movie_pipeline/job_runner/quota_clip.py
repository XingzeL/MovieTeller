from __future__ import annotations

import subprocess
from pathlib import Path

from media_utils.probe import ffprobe_path_for


def should_clip_video(
    *,
    start_point: float | None,
    end_point: float | None,
    source_path: str | Path,
) -> bool:
    if start_point is None and end_point is None:
        return False
    if end_point is not None and float(end_point) <= 0:
        return False
    return Path(source_path).is_file()


def clip_video_to_processed(
    *,
    source_path: str | Path,
    output_path: str | Path,
    start_point: float | None,
    end_point: float | None,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """Trim source video to [start_point, end_point) and write processed output."""
    src = Path(source_path)
    out = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source video not found: {src}")

    start = float(start_point or 0.0)
    end = float(end_point) if end_point is not None else None
    if end is not None and end <= start:
        raise ValueError("end_point must be greater than start_point")

    out.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
    ]
    if end is not None:
        duration = max(0.0, end - start)
        cmd.extend(["-i", str(src), "-t", str(duration)])
    else:
        cmd.extend(["-i", str(src)])
    cmd.extend(
        [
            "-c",
            "copy",
            str(out),
        ]
    )

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg clip failed ({proc.returncode}): {(proc.stderr or proc.stdout).strip()}"
        )
    if not out.is_file():
        raise RuntimeError(f"ffmpeg clip did not produce output: {out}")
    return out


def probe_duration_sec(media_path: str | Path, *, ffmpeg_bin: str = "ffmpeg") -> float:
    from media_utils.probe import probe_duration_sec as _probe

    return _probe(str(media_path), ffprobe_bin=ffprobe_path_for(ffmpeg_bin))
