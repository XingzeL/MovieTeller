from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from typing import Any, Callable

from pipeline_types import FrameBatch

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _split_png_blob(data: bytes) -> list[bytes]:
    if not data:
        return []
    chunks: list[bytes] = []
    positions: list[int] = []
    idx = 0
    while idx <= len(data) - len(PNG_SIGNATURE):
        pos = data.find(PNG_SIGNATURE, idx)
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


def _extract_frames_base64(
    video_path: str,
    *,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    max_frames: int,
    ffmpeg_bin: str,
    max_edge_pixels: int,
    subprocess_run: Callable[..., Any],
) -> tuple[str, ...]:
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if max_frames < 1:
        raise ValueError("max_frames must be >= 1")
    if max_edge_pixels < 16:
        raise ValueError("max_edge_pixels must be >= 16")
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")

    fps = max_frames / max(duration_sec, 1e-6)
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
    pngs = _split_png_blob(proc.stdout or b"")
    if not pngs:
        raise RuntimeError("ffmpeg produced no PNG frames")
    return tuple(
        base64.standard_b64encode(blob).decode("ascii")
        for blob in pngs[:max_frames]
    )


def sample_uniform_frames(
    *,
    video_path: str,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    ffmpeg_bin: str,
    max_frames: int,
    max_edge_pixels: int,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> FrameBatch:
    frames = _extract_frames_base64(
        video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration_sec,
        max_frames=max_frames,
        ffmpeg_bin=ffmpeg_bin,
        max_edge_pixels=max_edge_pixels,
        subprocess_run=subprocess_run,
    )
    count = len(frames)
    if count <= 0:
        raise RuntimeError("uniform frame extraction produced no frames")
    if start_sec is None or end_sec is None:
        if count == 1:
            frame_times = (duration_sec / 2.0,)
        else:
            frame_times = tuple(duration_sec * ((idx + 0.5) / count) for idx in range(count))
    else:
        span = end_sec - start_sec
        if count == 1:
            frame_times = (start_sec + span / 2.0,)
        else:
            frame_times = tuple(
                start_sec + span * ((idx + 0.5) / count) for idx in range(count)
            )
    return FrameBatch(
        frames_base64_png=tuple(frames),
        frame_times_sec=tuple(frame_times),
        duration_sec=float(duration_sec),
        source="uniform",
        shot_ids=None,
    )
