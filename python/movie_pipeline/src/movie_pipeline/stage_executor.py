from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import BoundedSemaphore
from typing import cast, TypeVar

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
        workers = max(1, int(concurrency))
        if workers == 1 or total == 1:
            out: list[R] = []
            for index, item in enumerate(values):
                try:
                    out.append(fn(item))
                except Exception as exc:
                    raise StageExecutionError(
                        StageItemError(stage=stage_name, index=index, message=str(exc))
                    ) from exc
                if progress is not None:
                    progress(stage_name, len(out), total)
            return tuple(out)

        results: list[R | object] = [_MISSING] * total
        completed = 0
        with ThreadPoolExecutor(max_workers=min(workers, total)) as pool:
            future_to_index = {
                pool.submit(fn, item): index for index, item in enumerate(values)
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
                if progress is not None:
                    progress(stage_name, completed, total)
        return tuple(cast(R, item) for item in results)
