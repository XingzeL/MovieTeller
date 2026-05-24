from __future__ import annotations

from typing import Any

try:
    from movieteller_logging import emit_event
except ImportError:  # pragma: no cover - optional dependency in minimal installs

    def emit_gateway_event(event: str, **kwargs: Any) -> None:
        _ = (event, kwargs)

else:

    def emit_gateway_event(event: str, **kwargs: Any) -> None:
        """Bridge for legacy callers; forwards to structured :func:`emit_event`."""
        emit_event(event, **kwargs)
