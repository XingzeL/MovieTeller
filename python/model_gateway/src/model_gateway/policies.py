from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

T = TypeVar("T")

_DEFAULT_LIMITS: dict[str, int] = {
    "openai_compatible": 4,
    "edge_tts": 2,
    "volcengine_tts": 2,
}
_LOCK = threading.Lock()
_LIMITERS: dict[str, threading.BoundedSemaphore] = {}


def _limiter_for(adapter: str) -> threading.BoundedSemaphore:
    with _LOCK:
        limiter = _LIMITERS.get(adapter)
        if limiter is None:
            limiter = threading.BoundedSemaphore(_DEFAULT_LIMITS.get(adapter, 4))
            _LIMITERS[adapter] = limiter
        return limiter


@contextmanager
def limited(adapter: str):
    limiter = _limiter_for(adapter)
    limiter.acquire()
    try:
        yield
    finally:
        limiter.release()


def execute_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 2,
) -> tuple[T, int]:
    last_exc: Exception | None = None
    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            return fn(), attempt - 1
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts:
                raise
    assert last_exc is not None
    raise last_exc
