from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from subtitle_extraction.parse_srt import parse_srt_text
from subtitle_extraction.types import ExtractionResult, SubtitleCue

_ALLOWED_ASR = frozenset({"bijian", "jianying", "whisper-api", "whisper-cpp"})


class TranscriptionError(RuntimeError):
    """videocaptioner transcribe failed."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


def resolve_videocaptioner_bin(explicit: str | None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    w = shutil.which("videocaptioner")
    if not w:
        raise TranscriptionError(
            "videocaptioner executable not found; set videocaptioner_bin or PATH",
        )
    return w


def build_transcribe_command(
    *,
    executable: str,
    input_path: str,
    output_srt_path: str,
    asr: str,
    language: str,
) -> list[str]:
    cmd = [
        executable,
        "transcribe",
        input_path,
        "-o",
        output_srt_path,
        "--format",
        "srt",
        "--quiet",
        "--asr",
        asr,
    ]
    lang = (language or "auto").strip().lower()
    if lang != "auto":
        cmd.extend(["--language", language.strip()])
    return cmd


def extract_subtitles(
    video_path: str,
    *,
    videocaptioner_bin: str | None = None,
    output_srt_path: str | None = None,
    asr: str = "bijian",
    language: str = "auto",
    timeout_sec: float | None = None,
    subprocess_run=subprocess.run,
) -> ExtractionResult:
    """
    Run ``videocaptioner transcribe`` and parse the resulting SRT.

    ``asr`` must be one of VideoCaptioner CLI choices:
    bijian, jianying, whisper-api, whisper-cpp.
    """
    path = Path(video_path)
    if not path.is_file():
        raise TranscriptionError(f"Input file not found: {path}")

    asr_norm = str(asr or "bijian").strip().lower()
    if asr_norm not in _ALLOWED_ASR:
        raise TranscriptionError(
            f"Unsupported videocaptioner_asr '{asr_norm}'. "
            f"Expected one of: {', '.join(sorted(_ALLOWED_ASR))}",
        )

    exe = resolve_videocaptioner_bin(videocaptioner_bin)
    tmp_path: Path | None = None
    if output_srt_path:
        out = Path(output_srt_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        srt_out = out
    else:
        fd, name = tempfile.mkstemp(suffix=".srt", prefix="movieteller_vc_")
        import os

        os.close(fd)
        tmp_path = Path(name)
        srt_out = tmp_path

    cmd = build_transcribe_command(
        executable=exe,
        input_path=str(path.resolve()),
        output_srt_path=str(srt_out.resolve()),
        asr=asr_norm,
        language=language or "auto",
    )

    sub_timeout = None if timeout_sec is None or timeout_sec <= 0 else timeout_sec

    try:
        proc = subprocess_run(
            cmd,
            capture_output=True,
            text=True,
            timeout=sub_timeout,
        )
    except subprocess.TimeoutExpired as e:
        msg = f"videocaptioner transcribe timed out after {timeout_sec}s"
        err_tail = ""
        if getattr(e, "stderr", None):
            err_tail = (e.stderr or "")[:8000]
        raise TranscriptionError(msg, stderr=err_tail) from e

    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise TranscriptionError(
            f"videocaptioner transcribe failed (exit {proc.returncode})",
            exit_code=proc.returncode,
            stderr=err[:8000],
        )

    if not srt_out.is_file():
        raise TranscriptionError(
            "Expected SRT output missing after transcribe",
            stderr=err[:8000],
        )

    raw = srt_out.read_text(encoding="utf-8", errors="replace")
    cues_list = parse_srt_text(raw)
    cues = tuple(cues_list)

    return ExtractionResult(subtitle_path=str(srt_out.resolve()), cues=cues)


def extract_subtitles_using_settings(video_path: str, settings: object) -> ExtractionResult:
    """Load ASR options from movieteller_config.Settings (duck-typed)."""
    bin_v = getattr(settings, "videocaptioner_bin", None)
    timeout_ms = getattr(settings, "videocaptioner_transcribe_timeout_ms", None)
    timeout_sec: float | None
    if timeout_ms is None:
        timeout_sec = None
    else:
        timeout_sec = max(1.0, float(timeout_ms) / 1000.0)

    return extract_subtitles(
        video_path,
        videocaptioner_bin=bin_v if isinstance(bin_v, str) or bin_v is None else str(bin_v),
        output_srt_path=None,
        asr=str(getattr(settings, "videocaptioner_asr", None) or "bijian"),
        language=str(getattr(settings, "videocaptioner_language", None) or "auto"),
        timeout_sec=timeout_sec,
    )
