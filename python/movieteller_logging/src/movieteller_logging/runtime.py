from __future__ import annotations

import atexit
import json
import logging
import logging.handlers
import queue
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from movieteller_logging.context import current_pipeline_extra

_LOGGER_NAME = "movieteller"
_EXTRA_KEYS = frozenset(
    {
        "event",
        "job_id",
        "stage",
        "group_index",
        "segment_index",
        "capability",
        "provider",
        "model",
        "adapter",
        "duration_ms",
        "status",
        "error_type",
        "error_message",
        "error_code",
        "retryable",
        "fatal",
        "retry_count",
        "completed",
        "total",
        "slug",
        "base_url",
        "frames",
        "source",
        "win_start",
        "win_end",
        "duration_sec",
        "passage_chars",
        "elapsed_ms",
    }
)

_LOGRECORD_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
    }
)

_queue: queue.Queue[logging.LogRecord | None] | None = None
_listener: logging.handlers.QueueListener | None = None
_root: logging.Logger | None = None
_handlers: list[logging.Handler] = []
_enabled = False
_atexit_registered = False


class _JsonlFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3] + "Z"
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _LOGRECORD_RESERVED or key.startswith("_"):
                continue
            if value is not None and (key in _EXTRA_KEYS or key.startswith("x_")):
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    payload[key] = str(value)
                else:
                    payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_async_logging(
    *,
    enabled: bool = False,
    level: str = "INFO",
    format: str = "jsonl",
    stderr: bool = True,
    file: str | None = None,
) -> None:
    """Start QueueListener + QueueHandler for logger ``movieteller`` (idempotent restart)."""
    global _queue, _listener, _root, _enabled, _handlers, _atexit_registered
    shutdown_async_logging()
    if not enabled:
        _enabled = False
        return
    if format.strip().lower() != "jsonl":
        raise ValueError("only format=jsonl is supported for now")
    level_no = getattr(logging, str(level or "INFO").upper(), logging.INFO)
    _queue = queue.Queue(-1)
    qh = logging.handlers.QueueHandler(_queue)
    root = logging.getLogger(_LOGGER_NAME)
    root.handlers.clear()
    root.setLevel(level_no)
    root.addHandler(qh)
    root.propagate = False
    handlers: list[logging.Handler] = []
    if stderr:
        sh = logging.StreamHandler()
        sh.setFormatter(_JsonlFormatter())
        sh.setLevel(level_no)
        handlers.append(sh)
    if file:
        path = Path(file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(_JsonlFormatter())
        fh.setLevel(level_no)
        handlers.append(fh)
    if not handlers:
        root.handlers.clear()
        _enabled = False
        return
    _listener = logging.handlers.QueueListener(_queue, *handlers, respect_handler_level=True)
    _listener.start()
    _handlers = handlers
    _root = root
    _enabled = True
    if not _atexit_registered:
        atexit.register(shutdown_async_logging)
        _atexit_registered = True


def shutdown_async_logging() -> None:
    global _queue, _listener, _root, _enabled, _handlers
    if _listener is not None:
        _listener.stop()
        _listener = None
    if _root is not None:
        _root.handlers.clear()
        _root = None
    for handler in _handlers:
        handler.close()
    _handlers = []
    _queue = None
    _enabled = False


def emit_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Enqueue one structured log line (merged with pipeline context). No-op if disabled."""
    if not _enabled or _root is None:
        return
    merged: dict[str, Any] = {**current_pipeline_extra(), "event": event, **fields}
    extra: dict[str, Any] = {}
    for key, value in merged.items():
        if value is None or key in _LOGRECORD_RESERVED:
            continue
        if key in _EXTRA_KEYS or (isinstance(key, str) and key.startswith("x_")):
            extra[key] = value
    extra["event"] = event
    _root.log(level, event, extra=extra)
