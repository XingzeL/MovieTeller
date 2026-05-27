"""TTY progress for local workflow runs: one in-place line, or sparse milestone lines."""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable, TextIO

from movieteller_logging.stage_registry import macro_label, macro_stage_ids

_WORKFLOW_STAGES: tuple[str, ...] = macro_stage_ids()

_SEGMENT_STEP_LABELS: dict[str, str] = {
    "context": "检索上下文",
    "narration": "生成旁白",
    "polish": "润色",
    "study": "学习卡",
    "tts": "语音合成",
}

_SEGMENT_STEP_MACRO: dict[str, str] = {
    "tts": "tts",
}

_SEGMENT_RENDER_INTERVAL_SEC = 0.35


def _bar(done: int, total: int, width: int = 12) -> str:
    if total <= 0:
        return "░" * width
    filled = min(width, int(width * done / total))
    return "█" * filled + "░" * (width - filled)


def _progress_enabled() -> bool:
    if os.environ.get("MOVIETELLER_NO_PROGRESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return False
    if os.environ.get("MOVIETELLER_FORCE_PROGRESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True
    return bool(sys.stdout.isatty() or sys.stderr.isatty())


def _progress_mode(stream: TextIO) -> str:
    """``inline`` = single ``\\r`` line; ``milestone`` = newline only when state changes."""
    raw = os.environ.get("MOVIETELLER_PROGRESS_MODE", "").strip().lower()
    if raw in {"inline", "milestone"}:
        return raw
    if hasattr(stream, "isatty") and stream.isatty():
        return "inline"
    return "milestone"


class CliProgressReporter:
    """Workflow progress without multi-line ANSI (avoids scrollback spam in many terminals)."""

    def __init__(self, *, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout
        self._mode = _progress_mode(self._stream)
        self._lock = threading.Lock()
        self._workflow_index = 0
        self._workflow_name = ""
        self._group_done = 0
        self._group_total = 0
        self._tts_total = 0
        self._tts_started_segments: set[int] = set()
        self._tts_done_segments: set[int] = set()
        self._segment_index: int | None = None
        self._segment_step = ""
        self._closed = False
        self._inline_active = False
        self._last_snapshot: str | None = None
        self._last_segment_render_at = 0.0

    @classmethod
    def enabled(cls) -> CliProgressReporter | None:
        if not _progress_enabled():
            return None
        return cls()

    def workflow_begin(self, name: str) -> None:
        with self._lock:
            self._workflow_name = name
            self._publish()

    def workflow_step_done(self, name: str) -> None:
        with self._lock:
            try:
                idx = _WORKFLOW_STAGES.index(name)
            except ValueError:
                idx = self._workflow_index
            next_index = min(len(_WORKFLOW_STAGES), idx + 1)
            if next_index > self._workflow_index or self._workflow_name == name:
                self._workflow_index = next_index
                self._workflow_name = name
                self._publish(force=True)

    def on_group(self, _stage: str, done: int, total: int) -> None:
        with self._lock:
            if self._workflow_name == "tts":
                return
            if done == self._group_done and total == self._group_total:
                return
            self._group_done = done
            self._group_total = total
            self._publish()

    def tts_begin(self, index: int, total: int) -> None:
        with self._lock:
            self._workflow_index = max(
                self._workflow_index,
                _WORKFLOW_STAGES.index("tts"),
            )
            self._workflow_name = "tts"
            self._tts_total = max(self._tts_total, int(total))
            self._tts_started_segments.add(int(index))
            self._segment_index = index
            self._segment_step = "tts"
            self._last_segment_render_at = time.monotonic()
            self._publish(force=True)

    def tts_done(self, index: int, total: int) -> None:
        with self._lock:
            self._workflow_index = max(
                self._workflow_index,
                _WORKFLOW_STAGES.index("tts"),
            )
            self._workflow_name = "tts"
            self._tts_total = max(self._tts_total, int(total))
            self._tts_done_segments.add(int(index))
            self._segment_index = index
            self._segment_step = "tts"
            self._last_segment_render_at = time.monotonic()
            self._publish(force=True)

    def segment_step(self, index: int, step: str) -> None:
        with self._lock:
            now = time.monotonic()
            unchanged = (
                self._segment_index == index and self._segment_step == step
            )
            if self._workflow_name == "tts" and step != "tts":
                return
            if unchanged and (now - self._last_segment_render_at) < _SEGMENT_RENDER_INTERVAL_SEC:
                return
            macro = _SEGMENT_STEP_MACRO.get(step)
            if macro in _WORKFLOW_STAGES:
                self._workflow_index = max(
                    self._workflow_index,
                    _WORKFLOW_STAGES.index(macro),
                )
                self._workflow_name = macro
            self._segment_index = index
            self._segment_step = step
            self._last_segment_render_at = now
            self._publish()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._inline_active:
                self._stream.write("\n")
                self._stream.flush()

    def _snapshot(self) -> str:
        wf_total = len(_WORKFLOW_STAGES)
        wf_label = macro_label(
            self._workflow_name,
            terminal=True,
        ) if self._workflow_name else "…"
        macro = (
            f"宏观 {_bar(self._workflow_index, wf_total)} "
            f"{self._workflow_index}/{wf_total} {wf_label}"
        )
        if self._group_total > 0:
            groups = (
                f"组 {_bar(self._group_done, self._group_total)} "
                f"{self._group_done}/{self._group_total}"
            )
        else:
            groups = "组 ·"
        if self._segment_index is not None and self._segment_step:
            seg_label = _SEGMENT_STEP_LABELS.get(self._segment_step, self._segment_step)
            segment = f"段 #{self._segment_index} {seg_label}"
            if self._workflow_name == "tts" and self._tts_total > 0:
                tts_done = min(self._tts_total, len(self._tts_done_segments))
                segment = (
                    f"段 #{self._segment_index} {seg_label} "
                    f"{_bar(tts_done, self._tts_total)} "
                    f"{tts_done}/{self._tts_total}"
                )
        else:
            segment = "段 ·"
        return f"[MovieTeller] {macro} | {groups} | {segment}"

    def _publish(self, *, force: bool = False) -> None:
        if self._closed:
            return
        line = self._snapshot()
        if not force and line == self._last_snapshot:
            return
        self._last_snapshot = line

        if self._mode == "inline":
            if not self._inline_active:
                self._inline_active = True
                self._stream.write("\n")
            self._stream.write(f"\r\x1b[2K{line}")
        else:
            self._stream.write(f"{line}\n")
        self._stream.flush()


def group_progress_callback(
    reporter: CliProgressReporter | None,
) -> Callable[[str, int, int], None] | None:
    if reporter is None:
        return None
    return reporter.on_group
