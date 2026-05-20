from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


def load_pipeline_speech_video_json(path: str | Path) -> dict[str, Any]:
    """Load a speech/render-stage pipeline JSON payload (e.g. ``*.manual.pipeline.speech.json``)."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at root, got {type(data).__name__}")
    return data


def _fmt_timecode(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    ms = int(round(sec * 1000.0))
    s, frac = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}.{frac:03d}"
    return f"{m:d}:{s:02d}.{frac:03d}"


def _str_clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


@dataclass(frozen=True)
class PipelineSpeechVideoScriptOptions:
    """Formatting options for :func:`build_readable_script`."""

    title: str | None = None
    """Optional document title (defaults to ``source_path`` stem when loading from file)."""

    include_raw_narration_if_different: bool = True
    """When ``text`` (vision narration) differs from ``speechText``, also emit the raw block."""

    include_speech_meta_one_liner: bool = False
    """Append a single line with voice / fitApplied when ``speech`` is present."""

    section_separator: str = "\n\n"
    """Between segment blocks."""


def build_readable_script(
    payload: Mapping[str, Any],
    *,
    source_path: str | Path | None = None,
    options: PipelineSpeechVideoScriptOptions | None = None,
) -> str:
    """
    Turn a pipeline speech/render JSON dict into a human-readable script.

    Each narrated segment includes subtitle context (``prevSubtitleText`` /
    ``nextSubtitleText``) and the narration / TTS line (``speechText`` or ``text``).
    """
    opts = options or PipelineSpeechVideoScriptOptions()
    lines: list[str] = []

    title = opts.title
    if title is None and source_path is not None:
        title = Path(source_path).stem
    if title:
        lines.append(title)
        lines.append("=" * min(len(title), 72))

    dur = payload.get("videoDurationSec")
    if isinstance(dur, (int, float)):
        lines.append(f"片长（秒）: {float(dur):.3f}")
    elif dur is not None:
        lines.append(f"片长: {dur}")

    segs = payload.get("narratedSegments")
    if not isinstance(segs, list):
        raise ValueError("payload['narratedSegments'] must be a non-empty list")
    if not segs:
        raise ValueError("payload['narratedSegments'] is empty")

    lines.append("")
    lines.append(f"共 {len(segs)} 段旁白时段")
    lines.append("")

    sep = opts.section_separator
    blocks: list[str] = []

    for i, raw in enumerate(segs, start=1):
        if not isinstance(raw, dict):
            raise TypeError(f"narratedSegments[{i - 1}] must be an object, got {type(raw).__name__}")
        start = float(raw["startSec"])
        end = float(raw["endSec"])
        duration = raw.get("durationSec")
        if isinstance(duration, (int, float)):
            dur_s = float(duration)
        else:
            dur_s = end - start

        prev_sub = _str_clean(raw.get("prevSubtitleText"))
        next_sub = _str_clean(raw.get("nextSubtitleText"))
        narration = _str_clean(raw.get("text"))
        speech_line = _str_clean(raw.get("speechText")) or narration

        bl: list[str] = []
        bl.append(f"--- 第 {i} 段 | {_fmt_timecode(start)} – {_fmt_timecode(end)}（{dur_s:.2f}s） ---")
        bl.append("")
        bl.append("【紧邻原片字幕 / 台词参考】")
        if prev_sub:
            bl.append(f"  前一条：{prev_sub}")
        else:
            bl.append("  前一条：（无）")
        if next_sub:
            bl.append(f"  后一条：{next_sub}")
        else:
            bl.append("  后一条：（无）")
        bl.append("")
        bl.append("【旁白 / 口播稿】")
        bl.append(speech_line or "（空）")

        if opts.include_raw_narration_if_different and narration and narration != speech_line:
            bl.append("")
            bl.append("【画面理解生成的原始旁白】（与口播稿不同）")
            bl.append(narration)

        speech = raw.get("speech")
        if opts.include_speech_meta_one_liner and isinstance(speech, dict):
            voice = _str_clean(speech.get("voice"))
            fit = speech.get("fitApplied")
            bl.append("")
            bl.append(
                f"（TTS：voice={voice or '—'}，fitApplied={fit!s}）"
            )

        blocks.append("\n".join(bl))

    lines.append(sep.join(blocks))
    return "\n".join(lines).rstrip() + "\n"
