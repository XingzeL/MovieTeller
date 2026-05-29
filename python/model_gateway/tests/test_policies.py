from __future__ import annotations

import pytest

from model_gateway.errors import (
    GatewayAuthError,
    GatewayConfigError,
    GatewayProviderError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    GatewayTransientError,
    GatewayUnsupportedCapabilityError,
)
from model_gateway.policies import execute_with_retry, is_retryable_exception


def test_execute_with_retry_stops_on_non_retryable() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise ValueError("401 authentication failed")

    with pytest.raises(ValueError):
        execute_with_retry(fn, max_attempts=3, is_retryable=is_retryable_exception)
    assert calls["n"] == 1


def test_execute_with_retry_retries_retryable() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("request timed out")
        return "ok"

    value, retry_count = execute_with_retry(
        fn, max_attempts=3, is_retryable=is_retryable_exception
    )
    assert value == "ok"
    assert retry_count == 1


def test_execute_with_retry_exhausts_max_attempts_on_retryable() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise TimeoutError("request timed out")

    with pytest.raises(TimeoutError):
        execute_with_retry(fn, max_attempts=2, is_retryable=is_retryable_exception)
    assert calls["n"] == 2


def test_execute_with_retry_single_attempt_skips_retry_even_if_retryable() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise TimeoutError("request timed out")

    with pytest.raises(TimeoutError):
        execute_with_retry(fn, max_attempts=1, is_retryable=is_retryable_exception)
    assert calls["n"] == 1


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (GatewayConfigError("bad config"), False),
        (GatewayUnsupportedCapabilityError("no adapter"), False),
        (GatewayAuthError("invalid key"), False),
        (GatewayTimeoutError("deadline"), True),
        (GatewayRateLimitError("429"), True),
        (GatewayTransientError("upstream blip"), True),
        (GatewayProviderError("Error code: 500 internal_server_error"), True),
        (GatewayProviderError("401 invalid token"), False),
        (GatewayProviderError("404 model not found"), False),
        (RuntimeError("connection reset"), True),
        (ValueError("bad prompt"), False),
    ],
)
def test_is_retryable_exception_matrix(exc: BaseException, expected: bool) -> None:
    assert is_retryable_exception(exc) is expected


def test_execute_with_retry_does_not_retry_gateway_config_error() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise GatewayConfigError("speech output_path is required")

    with pytest.raises(GatewayConfigError):
        execute_with_retry(fn, max_attempts=3, is_retryable=is_retryable_exception)
    assert calls["n"] == 1


def test_execute_with_retry_retries_gateway_provider_500() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise GatewayProviderError("HTTP 500 internal_server_error")
        return "ok"

    value, retry_count = execute_with_retry(
        fn, max_attempts=3, is_retryable=is_retryable_exception
    )
    assert value == "ok"
    assert retry_count == 1
