from __future__ import annotations

from typing import Any


def emit_gateway_event(event: str, **kwargs: Any) -> None:
    _ = (event, kwargs)
