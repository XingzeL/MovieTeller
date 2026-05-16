from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from media_utils import ffprobe_path_for, probe_duration_sec
from model_gateway import synthesize_speech
from model_gateway.types import SpeechRequest
from movieteller_config.schema import NarrationSpeechOptions

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
    return probe_duration_sec(
        media_path,
        ffprobe_bin=ffprobe_bin,
        subprocess_run=subprocess_run,
    )


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
def synthesize_narration_text(
    text: str,
    segment_duration_sec: float,
    *,
    output_path: str,
    metadata_path: str | None = None,
    target_duration_sec: float | None = None,
    options: NarrationSpeechOptions,
    settings: "Settings",
    communicator_factory: Callable[..., Any] | None = None,
    subprocess_run: Callable[..., Any] = subprocess.run,
) -> NarrationSpeechResult:
    raw_text = " ".join(str(text).split()).strip()
    if not raw_text:
        raise ValueError("speech text is empty")

    resolved_provider = options.provider_slug
    resolved_voice = options.voice
    resolved_rate = options.rate
    resolved_volume = options.volume
    resolved_pitch = options.pitch
    resolved_boundary = options.boundary
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
    ffprobe_bin = ffprobe_path_for(options.ffmpeg_bin)

    with tempfile.TemporaryDirectory(prefix="narration_speech_") as tmpdir:
        raw_audio_path = Path(tmpdir) / final_audio_path.name
        t0 = time.perf_counter()
        synthesize_speech(
            SpeechRequest(
                provider=resolved_provider,
                voice=resolved_voice,
                text=raw_text,
                model=options.model,
                rate=resolved_rate,
                volume=resolved_volume,
                pitch=resolved_pitch,
                boundary=resolved_boundary,
                output_path=str(raw_audio_path),
                metadata_path=str(metadata_file),
            ),
            settings=settings,
            communicator_factory=communicator_factory,
        )
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
                ffmpeg_bin=options.ffmpeg_bin,
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
