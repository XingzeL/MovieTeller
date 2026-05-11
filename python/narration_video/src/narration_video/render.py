from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from media_utils import ffprobe_path_for, probe_duration_sec
from movieteller_config import load_settings
from pipeline_types import NarrationAudioSegment

from narration_video.types import NarrationVideoRenderResult


def _video_has_audio_stream(
    video_path: str,
    *,
    ffprobe_bin: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> bool:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    proc = subprocess_run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe audio stream check failed ({proc.returncode}): {(proc.stderr or '').strip()}"
        )
    return bool((proc.stdout or "").strip())


def render_narrated_video(
    video_path: str,
    segments: Sequence[NarrationAudioSegment],
    *,
    output_path: str,
    background_audio_volume: float | None = None,
    speech_audio_volume: float | None = None,
    ffmpeg_bin: str | None = None,
    settings=None,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> NarrationVideoRenderResult:
    if not segments:
        raise ValueError("no narration audio segments were provided")
    src = Path(video_path)
    if not src.is_file():
        raise FileNotFoundError(f"Video not found: {src}")

    cfg = settings if settings is not None else load_settings()
    resolved_ffmpeg_bin = ffmpeg_bin or cfg.ffmpeg_path
    ffprobe_bin = ffprobe_path_for(resolved_ffmpeg_bin)
    video_duration_sec = probe_duration_sec(str(src), ffprobe_bin=ffprobe_bin)
    has_audio = _video_has_audio_stream(
        str(src), ffprobe_bin=ffprobe_bin, subprocess_run=subprocess_run
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    resolved_background_audio_volume = max(
        0.0,
        float(
            background_audio_volume
            if background_audio_volume is not None
            else cfg.narration_video_background_audio_volume
        ),
    )
    resolved_speech_audio_volume = max(
        0.0,
        float(
            speech_audio_volume
            if speech_audio_volume is not None
            else cfg.narration_video_speech_audio_volume
        ),
    )

    cmd: list[str] = [
        resolved_ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
    ]
    for seg in segments:
        audio = Path(seg.audio_path)
        if not audio.is_file():
            raise FileNotFoundError(f"Narration audio not found: {audio}")
        cmd.extend(["-i", str(audio)])

    filter_parts: list[str] = []
    if has_audio:
        filter_parts.append(
            f"[0:a]volume={resolved_background_audio_volume:.6f},apad,"
            f"atrim=0:{video_duration_sec:.6f}[base]"
        )
    else:
        filter_parts.append(
            f"anullsrc=channel_layout=stereo:sample_rate=24000,"
            f"atrim=0:{video_duration_sec:.6f}[base]"
        )

    mix_inputs = ["[base]"]
    for idx, seg in enumerate(segments, start=1):
        delay_ms = max(0, round(seg.start_sec * 1000.0))
        label = f"n{idx}"
        filter_parts.append(
            f"[{idx}:a]volume={resolved_speech_audio_volume:.6f},"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        mix_inputs.append(f"[{label}]")
    filter_parts.append(
        "".join(mix_inputs)
        + f"amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0[aout]"
    )
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )
    t0 = time.perf_counter()
    proc = subprocess_run(cmd, capture_output=True, text=True, check=False)
    timing_render_sec = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg video render failed ({proc.returncode}): {(proc.stderr or '').strip()}"
        )
    return NarrationVideoRenderResult(
        video_path=str(src),
        output_path=str(out),
        segment_count=len(segments),
        video_duration_sec=video_duration_sec,
        background_audio_volume=resolved_background_audio_volume,
        speech_audio_volume=resolved_speech_audio_volume,
        timing_render_sec=timing_render_sec,
    )
