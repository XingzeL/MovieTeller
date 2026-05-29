from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

from movieteller_logging import classify_error

from model_gateway.errors import (
    GatewayAuthError,
    GatewayConfigError,
    GatewayError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    GatewayTransientError,
    GatewayUnsupportedCapabilityError,
)

T = TypeVar("T")

_DEFAULT_LIMITS: dict[str, int] = {
    "openai_compatible": 4,
    "edge_tts": 2,
    "dashscope_tts": 2,
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


def is_retryable_exception(exc: BaseException) -> bool:
    """Whether ``execute_with_retry`` should attempt another call.

    Typed gateway errors are authoritative; everything else uses
    ``movieteller_logging.classify_error`` (string/heuristic based).
    """
    if isinstance(
        exc,
        (GatewayConfigError, GatewayUnsupportedCapabilityError, GatewayAuthError),
    ):
        return False
    if isinstance(
        exc,
        (GatewayTimeoutError, GatewayRateLimitError, GatewayTransientError),
    ):
        return True
    if isinstance(exc, GatewayError):
        return bool(classify_error(exc).get("retryable"))
    return bool(classify_error(exc).get("retryable"))


def execute_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 2,
    is_retryable: Callable[[BaseException], bool] | None = is_retryable_exception,
) -> tuple[T, int]:
    last_exc: Exception | None = None
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            return fn(), attempt - 1
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            if is_retryable is not None and not is_retryable(exc):
                raise
    assert last_exc is not None
    raise last_exc
