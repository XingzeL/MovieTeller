from __future__ import annotations

import base64
import subprocess
from pathlib import Path

from media_utils import ffprobe_path_for, probe_duration_sec, segment_duration_sec

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def split_png_blob(data: bytes) -> list[bytes]:
    """Split concatenated PNG streams (ffmpeg image2pipe) into individual images."""
    if not data:
        return []
    chunks: list[bytes] = []
    sig = PNG_SIGNATURE
    positions: list[int] = []
    idx = 0
    while idx <= len(data) - len(sig):
        pos = data.find(sig, idx)
        if pos == -1:
            break
        positions.append(pos)
        idx = pos + 1
    if not positions:
        return []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(data)
        chunks.append(data[start:end])
    return chunks


def extract_frames_base64(
    video_path: str,
    *,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    max_frames: int,
    ffmpeg_bin: str,
    max_edge_pixels: int = 768,
    subprocess_run=subprocess.run,
) -> list[str]:
    """
    Decode the segment with ffmpeg and emit up to ``max_frames`` PNG frames (base64, no data URL prefix).
    Uses interval decoding: ``-ss`` / ``-t`` when bounds are set; otherwise full file.
    """
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if max_frames < 1:
        raise ValueError("max_frames must be >= 1")
    if max_edge_pixels < 16:
        raise ValueError("max_edge_pixels must be >= 16")
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")

    # Spread ~max_frames samples across the segment: output fps = frames / duration
    fps = max_frames / max(duration_sec, 1e-6)
    # Fit inside edge×edge box; works for landscape, portrait, and square sources.
    e = max_edge_pixels
    vf = (
        f"fps=fps={fps:.6f},"
        f"scale={e}:{e}:force_original_aspect_ratio=decrease:flags=bicubic"
    )

    cmd: list[str] = [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if start_sec is not None and end_sec is not None:
        cmd.extend(["-ss", f"{start_sec:.6f}", "-i", str(path), "-t", f"{duration_sec:.6f}"])
    else:
        cmd.extend(["-i", str(path)])

    cmd.extend(
        [
            "-vf",
            vf,
            "-frames:v",
            str(max_frames),
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]
    )

    proc = subprocess_run(
        cmd,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err.strip()}")

    raw = proc.stdout or b""
    pngs = split_png_blob(raw)
    if not pngs:
        raise RuntimeError("ffmpeg produced no PNG frames")

    # ffmpeg may emit fewer than max_frames; cap defensively
    out: list[str] = []
    for blob in pngs[:max_frames]:
        out.append(base64.standard_b64encode(blob).decode("ascii"))
    return out
