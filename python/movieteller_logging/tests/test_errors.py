from __future__ import annotations

from movieteller_logging.errors import classify_error


def test_classify_error_detects_provider_500_as_retryable() -> None:
    fields = classify_error(RuntimeError("Error code: 500 internal_server_error"))

    assert fields["error_code"] == "provider_500"
    assert fields["retryable"] is True
    assert fields["error_type"] == "RuntimeError"


def test_classify_error_detects_auth_as_non_retryable() -> None:
    fields = classify_error(RuntimeError("Invalid token 401"))

    assert fields["error_code"] == "provider_auth_failed"
    assert fields["retryable"] is False


def test_classify_error_rate_limit_is_retryable() -> None:
    fields = classify_error(RuntimeError("429 rate limit exceeded"))

    assert fields["error_code"] == "provider_rate_limited"
    assert fields["retryable"] is True


def test_classify_error_timeout_is_retryable() -> None:
    fields = classify_error(TimeoutError("request timed out"))

    assert fields["error_code"] == "provider_timeout"
    assert fields["retryable"] is True


def test_classify_error_value_error_maps_to_invalid_request_non_retryable() -> None:
    fields = classify_error(ValueError("bad parameter"))

    assert fields["error_code"] == "invalid_request"
    assert fields["retryable"] is False
