from __future__ import annotations

from pathlib import Path

from movieteller_logging.context import (
    bind_pipeline_log_context,
    current_pipeline_extra,
    reset_pipeline_log_context,
)
from movieteller_config.schema import settings_from_dict
from subtitle_analysis.types import SubtitleAnalysisResult

from movie_pipeline.pipeline import narrate_analysis_candidates
from movie_pipeline.runtime_context import RunContext
from movie_pipeline.types import NarrationPipelineConfig


def test_narrate_analysis_candidates_preserves_x_output_root(tmp_path: Path) -> None:
    job_root = tmp_path / "job-ctx"
    job_root.mkdir()
    token = bind_pipeline_log_context(
        job_id="job-ctx",
        stage="workflow",
        x_output_root=str(job_root),
    )
    analysis = SubtitleAnalysisResult(
        video_duration_sec=10.0,
        subtitle_spans=(),
        raw_gaps=(),
        narration_candidates=(),
    )
    settings = settings_from_dict({})
    ctx = RunContext(
        settings=settings,
        pipeline=NarrationPipelineConfig(
            min_gap_sec=1.0,
            frame_source_options=object(),
        ),
    )
    try:
        result = narrate_analysis_candidates(
            analysis,
            ctx=ctx,
            video_path=str(tmp_path / "video.mp4"),
            job_id="job-ctx",
        )
        assert result == ()
        assert current_pipeline_extra().get("x_output_root") == str(job_root)
        assert current_pipeline_extra().get("job_id") == "job-ctx"
    finally:
        reset_pipeline_log_context(token)
