from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_pipeline_extra: ContextVar[dict[str, Any]] = ContextVar(
    "movieteller_pipeline_log_extra", default={}
)


def bind_pipeline_log_context(**kwargs: Any) -> Token:
    """Replace pipeline-wide log fields (e.g. ``job_id``, ``stage``) for this context."""
    return _pipeline_extra.set(dict(kwargs))


def merge_pipeline_context(**kwargs: Any) -> Token:
    """Shallow-merge fields into the current pipeline log context; returns token to reset."""
    cur = dict(_pipeline_extra.get())
    cur.update({k: v for k, v in kwargs.items() if v is not None})
    return _pipeline_extra.set(cur)


def reset_pipeline_log_context(token: Token) -> None:
    _pipeline_extra.reset(token)


def current_pipeline_extra() -> dict[str, Any]:
    return dict(_pipeline_extra.get())
