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
