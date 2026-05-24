from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventPage:
    events: tuple[dict[str, Any], ...]
    next_offset: int
    total_read: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_jsonl_events(path: str | Path) -> tuple[dict[str, Any], ...]:
    return tail_jsonl_events(path).events


def tail_jsonl_events(
    path: str | Path,
    *,
    after: int = 0,
    limit: int | None = None,
    level: str | None = None,
    stage: str | None = None,
) -> EventPage:
    """Read a JSONL event page from ``path``.

    ``after`` is a zero-based line offset, so callers can poll incrementally with
    the returned ``next_offset``. Filtering happens after parsing; ``next_offset``
    still advances over all physical lines read.
    """
    log_path = Path(path)
    if not log_path.is_file():
        return EventPage(events=(), next_offset=max(0, int(after)), total_read=0)

    start = max(0, int(after))
    max_items = None if limit is None else max(0, int(limit))
    level_filter = str(level).strip().upper() if level else None
    stage_filter = str(stage).strip() if stage else None
    events: list[dict[str, Any]] = []
    total_read = 0
    next_offset = start

    with log_path.open("r", encoding="utf-8") as fh:
        for line_index, line in enumerate(fh):
            if line_index < start:
                continue
            next_offset = line_index + 1
            total_read += 1
            row = _parse_json_line(line)
            if row is None:
                continue
            if level_filter and str(row.get("level") or "").upper() != level_filter:
                continue
            if stage_filter and str(row.get("stage") or "") != stage_filter:
                continue
            events.append(row)
            if max_items is not None and len(events) >= max_items:
                break

    return EventPage(events=tuple(events), next_offset=next_offset, total_read=total_read)


def _parse_json_line(line: str) -> dict[str, Any] | None:
    text = line.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
