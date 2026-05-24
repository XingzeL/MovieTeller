from __future__ import annotations

from typing import Any


def classify_error(exc: BaseException, *, default_code: str | None = None) -> dict[str, Any]:
    """Return stable logging fields for an exception.

    The classifier intentionally stays small and string-based for now so callers do not
    need to depend on provider SDK exception classes.
    """
    message = str(exc)
    lowered = message.lower()
    error_type = type(exc).__name__
    code = default_code or _code_from_message(error_type=error_type, lowered=lowered)
    return {
        "error_type": error_type,
        "error_message": message,
        "error_code": code,
        "retryable": _is_retryable(code),
    }


def _code_from_message(*, error_type: str, lowered: str) -> str:
    if "authentication" in error_type.lower() or "invalid token" in lowered or "401" in lowered:
        return "provider_auth_failed"
    if "rate" in lowered or "429" in lowered:
        return "provider_rate_limited"
    if "timeout" in lowered or "timed out" in lowered:
        return "provider_timeout"
    if "500" in lowered or "internal_server_error" in lowered:
        return "provider_500"
    if "not found" in lowered or "404" in lowered:
        return "provider_not_found"
    if "json" in lowered and ("decode" in lowered or "parse" in lowered):
        return "invalid_model_response"
    if error_type in {"FileNotFoundError"}:
        return "artifact_missing"
    if error_type in {"ValueError", "TypeError"}:
        return "invalid_request"
    return "internal_error"


def _is_retryable(code: str) -> bool:
    return code in {
        "provider_500",
        "provider_timeout",
        "provider_rate_limited",
        "internal_error",
    }
