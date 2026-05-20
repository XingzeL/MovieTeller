"""Formal pipeline stage: merge extracted SRT with narration timeline JSON."""

from __future__ import annotations

from narration_video.subtitles import (
    NarrationSubtitleBuildResult,
    build_subtitled_narration_srt,
)


def merge_subtitles_for_narration(
    *,
    speech_video_json_path: str,
    source_srt_path: str,
    output_srt_path: str,
) -> NarrationSubtitleBuildResult:
    """``speech_video.json`` + ``extracted.srt`` -> final merged ``.srt``."""
    return build_subtitled_narration_srt(
        speech_video_json_path=speech_video_json_path,
        source_srt_path=source_srt_path,
        output_srt_path=output_srt_path,
    )
