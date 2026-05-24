from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import BoundedSemaphore
from typing import cast, TypeVar

from movieteller_logging import emit_event, merge_pipeline_context, reset_pipeline_log_context

T = TypeVar("T")
R = TypeVar("R")
_MISSING = object()


@dataclass(frozen=True)
class StageItemError:
    stage: str
    index: int
    message: str
    retryable: bool = True


class StageExecutionError(RuntimeError):
    def __init__(self, error: StageItemError) -> None:
        super().__init__(f"{error.stage}[{error.index}] failed: {error.message}")
        self.error = error


class CapabilityLimiter:
    def __init__(self, concurrency: int) -> None:
        self._sem = BoundedSemaphore(max(1, int(concurrency)))

    def __enter__(self) -> CapabilityLimiter:
        self._sem.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._sem.release()


@dataclass(frozen=True)
class CapabilityLimiters:
    narration: CapabilityLimiter
    polish: CapabilityLimiter
    study_enrichment: CapabilityLimiter
    tts: CapabilityLimiter
    subtitle_context: CapabilityLimiter

    @classmethod
    def from_options(cls, options) -> CapabilityLimiters:
        return cls(
            narration=CapabilityLimiter(options.narration),
            polish=CapabilityLimiter(options.polish),
            study_enrichment=CapabilityLimiter(options.study_enrichment),
            tts=CapabilityLimiter(options.tts),
            subtitle_context=CapabilityLimiter(options.subtitle_context),
        )


class StageExecutor:
    def map_ordered(
        self,
        items: Iterable[T],
        fn: Callable[[T], R],
        *,
        concurrency: int,
        stage_name: str,
        progress: Callable[[str, int, int], None] | None = None,
    ) -> tuple[R, ...]:
        values = tuple(items)
        total = len(values)
        if total == 0:
            return ()

        def _emit_progress(done: int) -> None:
            emit_event(
                "stage.group.progress",
                stage=stage_name,
                completed=done,
                total=total,
                status="ok",
            )
            if progress is not None:
                progress(stage_name, done, total)

        def _execute_one(index: int, item: T) -> R:
            group_index = index + 1
            log_token = merge_pipeline_context(group_index=group_index)
            emit_event(
                "stage.group.start",
                stage=stage_name,
                group_index=group_index,
                total=total,
            )
            t0 = time.perf_counter()
            try:
                result = fn(item)
            except BaseException as exc:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                emit_event(
                    "stage.group.failed",
                    level=logging.ERROR,
                    stage=stage_name,
                    group_index=group_index,
                    total=total,
                    duration_ms=duration_ms,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                raise
            else:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                emit_event(
                    "stage.group.done",
                    stage=stage_name,
                    group_index=group_index,
                    total=total,
                    duration_ms=duration_ms,
                    status="ok",
                )
                return result
            finally:
                reset_pipeline_log_context(log_token)

        workers = max(1, int(concurrency))
        if workers == 1 or total == 1:
            out: list[R] = []
            for index, item in enumerate(values):
                try:
                    out.append(_execute_one(index, item))
                except Exception as exc:
                    raise StageExecutionError(
                        StageItemError(stage=stage_name, index=index, message=str(exc))
                    ) from exc
                _emit_progress(len(out))
            return tuple(out)

        results: list[R | object] = [_MISSING] * total
        completed = 0
        with ThreadPoolExecutor(max_workers=min(workers, total)) as pool:
            future_to_index = {
                pool.submit(_execute_one, index, item): index
                for index, item in enumerate(values)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as exc:
                    raise StageExecutionError(
                        StageItemError(stage=stage_name, index=index, message=str(exc))
                    ) from exc
                completed += 1
                _emit_progress(completed)
        return tuple(cast(R, item) for item in results)
