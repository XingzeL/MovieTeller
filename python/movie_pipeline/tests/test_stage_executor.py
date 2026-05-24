import time
from threading import Lock

import pytest

from movie_pipeline.stage_executor import (
    CapabilityLimiter,
    CapabilityLimiters,
    StageExecutionError,
    StageExecutor,
)
from movieteller_logging import (
    bind_pipeline_log_context,
    reset_pipeline_log_context,
)
from movieteller_logging.context import current_pipeline_extra
from movieteller_config.schema import settings_from_dict


def test_map_ordered_preserves_input_order_when_completion_order_differs():
    executor = StageExecutor()

    def run(item: int) -> int:
        time.sleep(0.01 * (4 - item))
        return item * 10

    assert executor.map_ordered([1, 2, 3], run, concurrency=3, stage_name="demo") == (
        10,
        20,
        30,
    )


def test_map_ordered_preserves_none_results():
    executor = StageExecutor()

    assert executor.map_ordered([1, 2], lambda _item: None, concurrency=2, stage_name="demo") == (
        None,
        None,
    )


def test_map_ordered_serial_path_reports_progress():
    executor = StageExecutor()
    progress: list[tuple[str, int, int]] = []

    result = executor.map_ordered(
        ["a", "b"],
        lambda item: item.upper(),
        concurrency=1,
        stage_name="serial",
        progress=lambda stage, done, total: progress.append((stage, done, total)),
    )

    assert result == ("A", "B")
    assert progress == [("serial", 1, 2), ("serial", 2, 2)]


def test_map_ordered_wraps_item_failures_with_stage_and_index():
    executor = StageExecutor()

    def run(item: int) -> int:
        if item == 2:
            raise ValueError("boom")
        return item

    with pytest.raises(StageExecutionError) as exc_info:
        executor.map_ordered([1, 2, 3], run, concurrency=1, stage_name="explode")

    assert exc_info.value.error.stage == "explode"
    assert exc_info.value.error.index == 1
    assert "boom" in exc_info.value.error.message


def test_capability_limiter_enforces_max_concurrency():
    limiter = CapabilityLimiter(2)
    current = 0
    peak = 0
    lock = Lock()

    def run(item: int) -> int:
        nonlocal current, peak
        with limiter:
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.01)
            with lock:
                current -= 1
        return item

    assert StageExecutor().map_ordered(range(6), run, concurrency=6, stage_name="limited") == tuple(
        range(6)
    )
    assert peak == 2


def test_map_ordered_parallel_path_preserves_log_context():
    token = bind_pipeline_log_context(job_id="job-ctx", stage="outer")
    try:
        result = StageExecutor().map_ordered(
            [1, 2, 3],
            lambda _item: current_pipeline_extra().get("job_id"),
            concurrency=3,
            stage_name="context",
        )
    finally:
        reset_pipeline_log_context(token)

    assert result == ("job-ctx", "job-ctx", "job-ctx")


def test_capability_limiters_build_from_settings_options():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "model_defaults": {
                "narration": "narration-model",
                "polish": "polish-model",
                "tts": "tts-model",
                "embedding": "embedding-model",
            },
            "capability_concurrency": {
                "narration": 1,
                "polish": 2,
                "study_enrichment": 3,
                "tts": 4,
                "subtitle_context": 5,
            },
        }
    )

    limiters = CapabilityLimiters.from_options(settings.capability_concurrency_options())

    assert isinstance(limiters.narration, CapabilityLimiter)
    assert isinstance(limiters.polish, CapabilityLimiter)
    assert isinstance(limiters.study_enrichment, CapabilityLimiter)
    assert isinstance(limiters.tts, CapabilityLimiter)
    assert isinstance(limiters.subtitle_context, CapabilityLimiter)
