from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from edge_tts import Communicate
from movieteller_config import load_settings

from narration.frames import ffprobe_path_for
from narration_speech.types import NarrationSpeechResult

if TYPE_CHECKING:
    from movieteller_config.schema import Settings

_FIT_TOLERANCE_SEC = 0.05


def _probe_media_duration_sec(
    media_path: str,
    *,
    ffprobe_bin: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> float:
    path = Path(media_path)
    if not path.is_file():
        raise FileNotFoundError(f"Media not found: {path}")
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
    proc = subprocess_run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed ({proc.returncode}): {(proc.stderr or '').strip()}"
        )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError("ffprobe returned empty duration")
    return float(raw)


def _atempo_filter_for_speed(speed: float) -> str:
    if speed <= 0:
        raise ValueError("speed must be positive")
    remaining = float(speed)
    parts: list[str] = []
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.6f}")
    return ",".join(parts)


def _fit_audio_speedup(
    input_path: str,
    output_path: str,
    *,
    target_duration_sec: float,
    raw_duration_sec: float,
    ffmpeg_bin: str,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> None:
    speed = raw_duration_sec / target_duration_sec
    cmd = [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-filter:a",
        _atempo_filter_for_speed(speed),
        str(output_path),
    ]
    proc = subprocess_run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio fit failed ({proc.returncode}): {(proc.stderr or '').strip()}"
        )


def _communicator_factory(
    text: str,
    voice: str,
    *,
    rate: str,
    volume: str,
    pitch: str,
    boundary: str,
) -> Any:
    return Communicate(
        text,
        voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        boundary=boundary,
    )


def synthesize_narration_text(
    text: str,
    segment_duration_sec: float,
    *,
    output_path: str,
    metadata_path: str | None = None,
    target_duration_sec: float | None = None,
    provider_slug: str | None = None,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
    pitch: str | None = None,
    boundary: str | None = None,
    settings: "Settings | None" = None,
    communicator_factory: Callable[..., Any] | None = None,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> NarrationSpeechResult:
    raw_text = " ".join(str(text).split()).strip()
    if not raw_text:
        raise ValueError("speech text is empty")

    cfg = settings if settings is not None else load_settings()
    resolved_provider = (
        str(provider_slug or getattr(cfg, "narration_speech_provider", "edge_tts"))
        .strip()
        .lower()
        or "edge_tts"
    )
    if resolved_provider != "edge_tts":
        raise ValueError(
            f"Unsupported narration_speech provider '{resolved_provider}'; only edge_tts is implemented"
        )
    resolved_voice = (
        str(voice or getattr(cfg, "narration_speech_voice", "")).strip()
        or "en-US-EmmaMultilingualNeural"
    )
    resolved_rate = (
        str(rate or getattr(cfg, "narration_speech_rate", "+0%")).strip() or "+0%"
    )
    resolved_volume = (
        str(volume or getattr(cfg, "narration_speech_volume", "+0%")).strip() or "+0%"
    )
    resolved_pitch = (
        str(pitch or getattr(cfg, "narration_speech_pitch", "+0Hz")).strip() or "+0Hz"
    )
    resolved_boundary = (
        str(boundary or getattr(cfg, "narration_speech_boundary", "SentenceBoundary")).strip()
        or "SentenceBoundary"
    )
    resolved_target_duration_sec = max(
        0.1,
        float(
            target_duration_sec
            if target_duration_sec is not None
            else segment_duration_sec
        ),
    )

    final_audio_path = Path(output_path)
    final_audio_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_file = (
        Path(metadata_path)
        if metadata_path is not None
        else final_audio_path.with_suffix(final_audio_path.suffix + ".jsonl")
    )
    ffprobe_bin = ffprobe_path_for(cfg.ffmpeg_path)

    with tempfile.TemporaryDirectory(prefix="narration_speech_") as tmpdir:
        raw_audio_path = Path(tmpdir) / final_audio_path.name
        factory = communicator_factory or _communicator_factory
        communicate = factory(
            raw_text,
            resolved_voice,
            rate=resolved_rate,
            volume=resolved_volume,
            pitch=resolved_pitch,
            boundary=resolved_boundary,
        )
        t0 = time.perf_counter()
        asyncio.run(communicate.save(str(raw_audio_path), str(metadata_file)))
        t1 = time.perf_counter()

        raw_duration_sec = _probe_media_duration_sec(
            str(raw_audio_path),
            ffprobe_bin=ffprobe_bin,
            subprocess_run=subprocess_run,
        )
        fit_applied = raw_duration_sec > (resolved_target_duration_sec + _FIT_TOLERANCE_SEC)
        timing_fit_sec: float | None = None
        if fit_applied:
            t_fit0 = time.perf_counter()
            _fit_audio_speedup(
                str(raw_audio_path),
                str(final_audio_path),
                target_duration_sec=resolved_target_duration_sec,
                raw_duration_sec=raw_duration_sec,
                ffmpeg_bin=cfg.ffmpeg_path,
                subprocess_run=subprocess_run,
            )
            timing_fit_sec = time.perf_counter() - t_fit0
        else:
            os.replace(raw_audio_path, final_audio_path)

    audio_duration_sec = _probe_media_duration_sec(
        str(final_audio_path),
        ffprobe_bin=ffprobe_bin,
        subprocess_run=subprocess_run,
    )
    return NarrationSpeechResult(
        text=raw_text,
        segment_duration_sec=float(segment_duration_sec),
        target_duration_sec=resolved_target_duration_sec,
        audio_path=str(final_audio_path),
        metadata_path=str(metadata_file),
        raw_duration_sec=raw_duration_sec,
        audio_duration_sec=audio_duration_sec,
        provider=resolved_provider,
        voice=resolved_voice,
        rate=resolved_rate,
        volume=resolved_volume,
        pitch=resolved_pitch,
        boundary=resolved_boundary,
        fit_applied=fit_applied,
        timing_tts_sec=t1 - t0,
        timing_fit_sec=timing_fit_sec,
    )
