from __future__ import annotations

import json
from pathlib import Path

from movieteller_logging.reader import read_jsonl_events, tail_jsonl_events


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_tail_jsonl_events_reads_page_with_offset_and_limit(tmp_path: Path) -> None:
    log_path = tmp_path / "workflow.jsonl"
    _write_jsonl(
        log_path,
        [
            {"event": "a", "level": "INFO"},
            {"event": "b", "level": "INFO"},
            {"event": "c", "level": "INFO"},
        ],
    )

    page = tail_jsonl_events(log_path, after=1, limit=1)

    assert [row["event"] for row in page.events] == ["b"]
    assert page.next_offset == 2
    assert page.total_read == 1
    assert page.to_dict()["next_offset"] == 2


def test_tail_jsonl_events_filters_level_and_stage(tmp_path: Path) -> None:
    log_path = tmp_path / "workflow.jsonl"
    _write_jsonl(
        log_path,
        [
            {"event": "a", "level": "INFO", "stage": "narration"},
            {"event": "b", "level": "ERROR", "stage": "narration"},
            {"event": "c", "level": "ERROR", "stage": "render"},
        ],
    )

    page = tail_jsonl_events(log_path, level="ERROR", stage="narration")

    assert [row["event"] for row in page.events] == ["b"]
    assert page.next_offset == 3
    assert page.total_read == 3


def test_read_jsonl_events_skips_invalid_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "workflow.jsonl"
    log_path.write_text('{"event":"a"}\nnot-json\n{"event":"b"}', encoding="utf-8")

    rows = read_jsonl_events(log_path)

    assert [row["event"] for row in rows] == ["a", "b"]


def test_tail_jsonl_events_missing_file_returns_empty_page(tmp_path: Path) -> None:
    page = tail_jsonl_events(tmp_path / "missing.jsonl", after=5)

    assert page.events == ()
    assert page.next_offset == 5
    assert page.total_read == 0
