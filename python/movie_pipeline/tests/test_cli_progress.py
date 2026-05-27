from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_cli_progress_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "movie_pipeline"
        / "cli_progress.py"
    )
    spec = importlib.util.spec_from_file_location("movie_pipeline_cli_progress", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cli = _load_cli_progress_module()
CliProgressReporter = _cli.CliProgressReporter
_bar = _cli._bar
group_progress_callback = _cli.group_progress_callback


def test_bar_renders_partial_fill() -> None:
    assert _bar(1, 2, width=4) == "██░░"


def test_group_progress_callback_none_when_reporter_disabled() -> None:
    assert group_progress_callback(None) is None


def test_enabled_returns_none_when_not_tty_and_not_forced(monkeypatch) -> None:
    class _Stream:
        def isatty(self) -> bool:
            return False

    monkeypatch.delenv("MOVIETELLER_FORCE_PROGRESS", raising=False)
    monkeypatch.setattr(_cli.sys, "stdout", _Stream())
    monkeypatch.setattr(_cli.sys, "stderr", _Stream())
    assert CliProgressReporter.enabled() is None


def test_enabled_with_force_progress(monkeypatch) -> None:
    class _Stream:
        def isatty(self) -> bool:
            return False

    monkeypatch.setenv("MOVIETELLER_FORCE_PROGRESS", "1")
    monkeypatch.setattr(_cli.sys, "stdout", _Stream())
    monkeypatch.setattr(_cli.sys, "stderr", _Stream())
    assert CliProgressReporter.enabled() is not None


def test_milestone_mode_dedupes_identical_snapshot(capsys) -> None:
    import io

    stream = io.StringIO()
    stream.isatty = lambda: False  # type: ignore[attr-defined]
    reporter = _cli.CliProgressReporter(stream=stream)
    assert reporter._mode == "milestone"
    reporter.workflow_begin("subtitle_extraction")
    reporter.workflow_begin("subtitle_extraction")
    out = stream.getvalue()
    assert out.count("[MovieTeller]") == 1


def test_inline_mode_uses_carriage_return(capsys) -> None:
    import io

    stream = io.StringIO()
    stream.isatty = lambda: True  # type: ignore[attr-defined]
    reporter = _cli.CliProgressReporter(stream=stream)
    assert reporter._mode == "inline"
    reporter.workflow_begin("frame_pool")
    reporter.on_group("narration_group", 1, 3)
    body = stream.getvalue()
    assert "\r" in body
    assert body.count("\n") == 1


def test_tts_segment_step_advances_macro_stage() -> None:
    import io

    stream = io.StringIO()
    stream.isatty = lambda: False  # type: ignore[attr-defined]
    reporter = _cli.CliProgressReporter(stream=stream)
    reporter.workflow_begin("narration")
    reporter.segment_step(1, "tts")
    reporter.workflow_step_done("narration")
    out = stream.getvalue()
    assert "语音合成" in out
    assert "4/7" in out.splitlines()[-1]


def test_tts_progress_tracks_completed_segments() -> None:
    import io

    stream = io.StringIO()
    stream.isatty = lambda: False  # type: ignore[attr-defined]
    reporter = _cli.CliProgressReporter(stream=stream)
    reporter.tts_begin(1, 3)
    reporter.tts_done(1, 3)
    reporter.tts_begin(3, 3)
    out = stream.getvalue()
    assert "段 #1 语音合成" in out
    assert "1/3" in out
    assert "段 #3 语音合成" in out.splitlines()[-1]
    assert "1/3" in out.splitlines()[-1]
