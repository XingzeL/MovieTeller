"""Subtitle extraction via VideoCaptioner CLI + SRT parsing."""

from subtitle_extraction.parse_srt import parse_srt_text
from subtitle_extraction.transcribe import (
    TranscriptionError,
    build_transcribe_command,
    extract_subtitles,
    extract_subtitles_using_settings,
    resolve_videocaptioner_bin,
)
from subtitle_extraction.types import ExtractionResult, SubtitleCue

__all__ = [
    "ExtractionResult",
    "SubtitleCue",
    "TranscriptionError",
    "build_transcribe_command",
    "extract_subtitles",
    "extract_subtitles_using_settings",
    "parse_srt_text",
    "resolve_videocaptioner_bin",
]
