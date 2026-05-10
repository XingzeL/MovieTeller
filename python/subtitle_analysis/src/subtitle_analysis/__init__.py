from subtitle_analysis.analyze import (
    analyze_srt_text,
    analyze_subtitle_cues,
    analyze_subtitle_file,
    probe_video_duration_sec,
    result_to_dict,
    result_to_json,
)
from subtitle_analysis.types import (
    NarratedSegment,
    NarrationCandidate,
    NarrationPolishDetails,
    NarrationSpeechDetails,
    SubtitleAnalysisResult,
    TimeSpan,
)


def narrate_analysis_candidates(*args, **kwargs):
    from subtitle_analysis.pipeline import narrate_analysis_candidates as _impl

    return _impl(*args, **kwargs)


def analyze_and_narrate(*args, **kwargs):
    from subtitle_analysis.pipeline import analyze_and_narrate as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "TimeSpan",
    "NarrationCandidate",
    "NarratedSegment",
    "NarrationPolishDetails",
    "NarrationSpeechDetails",
    "SubtitleAnalysisResult",
    "probe_video_duration_sec",
    "analyze_subtitle_cues",
    "analyze_srt_text",
    "analyze_subtitle_file",
    "narrate_analysis_candidates",
    "analyze_and_narrate",
    "result_to_dict",
    "result_to_json",
]
