from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING, Callable

from model_gateway import polish_text as gateway_polish_text
from movieteller_config.schema import NarrationPolishOptions

from narration_polish.prompts import (
    build_system_message,
    build_title_only_system_message,
    build_title_only_user_message,
    build_user_message,
)
from narration_polish.types import NarrationPolishResult

if TYPE_CHECKING:
    from movieteller_config.schema import Settings

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")

def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def estimate_speech_duration_sec(text: str, speaking_rate_wpm: int) -> float:
    wpm = max(1, int(speaking_rate_wpm))
    return count_words(text) * 60.0 / float(wpm)


def compute_target_duration_sec(
    segment_duration_sec: float, safety_margin_sec: float
) -> float:
    return max(0.2, float(segment_duration_sec) - max(0.0, float(safety_margin_sec)))


def compute_target_word_count(
    segment_duration_sec: float,
    speaking_rate_wpm: int,
    safety_margin_sec: float,
) -> int:
    target_duration_sec = compute_target_duration_sec(
        segment_duration_sec, safety_margin_sec
    )
    return max(1, math.floor(target_duration_sec * max(1, int(speaking_rate_wpm)) / 60.0))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_polish_response(raw: str) -> tuple[str | None, str, bool]:
    """Parse model output into (Chinese title or None, English body, structured).

    *structured* is True when any non-empty line starts with ``TITLE:`` or ``BODY:``
    (case-insensitive). Otherwise the whole string is treated as legacy plain body
    only (no title, no second API call).
    """
    text = raw.strip()
    if not text:
        return None, "", False
    lines = raw.splitlines()
    stripped_nonempty = [ln.strip() for ln in lines if ln.strip()]
    structured = any(
        ln.upper().startswith("TITLE:") or ln.upper().startswith("BODY:")
        for ln in stripped_nonempty
    )
    if not structured:
        return None, _normalize_text(text), False

    title_val: str | None = None
    body_chunks: list[str] = []
    body_started = False
    title_line_idx: int | None = None

    for i, ln in enumerate(lines):
        s = ln.strip()
        ul = s.upper()
        if ul.startswith("TITLE:"):
            title_val = s.split(":", 1)[1].strip()
            title_line_idx = i
        elif ul.startswith("BODY:"):
            body_started = True
            body_chunks.append(s.split(":", 1)[1].strip())
        elif body_started:
            body_chunks.append(s.strip())

    body = _normalize_text(" ".join(body_chunks))
    if not body and title_line_idx is not None:
        tail = "\n".join(lines[title_line_idx + 1 :]).strip()
        body = _normalize_text(tail)

    return title_val, body, True


def _title_ok(title: str | None) -> bool:
    if title is None:
        return False
    u = title.strip()
    return bool(u) and len(u) <= 10


def _sanitize_scene_title_line(raw: str) -> str:
    line = raw.strip().splitlines()[0].strip() if raw.strip() else ""
    line = line.strip("\"'「」『』")
    if len(line) > 10:
        return line[:10]
    return line


def _truncate_to_word_budget(text: str, target_word_count: int) -> str:
    normalized = _normalize_text(text)
    budget = max(1, int(target_word_count))
    if count_words(normalized) <= budget:
        return normalized

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    kept: list[str] = []
    used = 0
    for sentence in sentences:
        words = count_words(sentence)
        if words == 0:
            continue
        if used + words > budget:
            break
        kept.append(sentence)
        used += words
    if kept and used > 0:
        candidate = _normalize_text(" ".join(kept))
        if count_words(candidate) <= budget:
            return candidate

    out: list[str] = []
    used = 0
    for token in normalized.split():
        words = count_words(token)
        if words == 0:
            if out:
                out.append(token)
            continue
        if used + words > budget:
            break
        out.append(token)
        used += words

    candidate = _normalize_text(" ".join(out)).rstrip(",;:-")
    if candidate and candidate[-1] not in ".!?":
        candidate += "."
    while candidate and count_words(candidate) > budget:
        candidate = _normalize_text(" ".join(candidate.split()[:-1])).rstrip(",;:-")
        if candidate and candidate[-1] not in ".!?":
            candidate += "."
    return candidate or normalized


def polish_narration_text(
    text: str,
    duration_sec: float,
    *,
    options: NarrationPolishOptions,
    settings: "Settings",
    client_factory: Callable[..., Any] | None = None,
) -> NarrationPolishResult:
    raw_text = _normalize_text(text)
    if not raw_text:
        raise ValueError("narration text is empty")

    resolved_target_wpm = options.target_wpm
    resolved_cefr_level = options.cefr_level
    resolved_strength = options.strength
    resolved_safety_margin_sec = options.safety_margin_sec
    resolved_prompt_style = options.prompt_style
    target_duration_sec = compute_target_duration_sec(
        duration_sec, resolved_safety_margin_sec
    )
    target_word_count = compute_target_word_count(
        duration_sec, resolved_target_wpm, resolved_safety_margin_sec
    )
    original_word_count = count_words(raw_text)
    estimated_original_duration_sec = estimate_speech_duration_sec(
        raw_text, resolved_target_wpm
    )
    messages = [
        {
            "role": "system",
            "content": build_system_message(
                cefr_level=resolved_cefr_level,
                strength=resolved_strength,
                style=resolved_prompt_style,
            ),
        },
        {
            "role": "user",
            "content": build_user_message(
                text=raw_text,
                segment_duration_sec=duration_sec,
                target_duration_sec=target_duration_sec,
                target_wpm=resolved_target_wpm,
                target_word_count=target_word_count,
                strength=resolved_strength,
            ),
        },
    ]

    t0 = time.perf_counter()
    result = gateway_polish_text(
        messages=messages,
        settings=settings,
        client_factory=client_factory,
    )
    t1 = time.perf_counter()
    timing_api_sec = t1 - t0

    content = result.text.strip()
    if not content:
        raise RuntimeError("Model returned empty polished narration text")

    parsed_title, parsed_body, structured = parse_polish_response(content)
    if structured and not parsed_body:
        raise RuntimeError("Model returned structured polish but empty BODY text")
    body_for_budget = parsed_body if parsed_body else _normalize_text(content)
    if not body_for_budget:
        raise RuntimeError("Model returned empty polished narration text")

    polished_text = _truncate_to_word_budget(body_for_budget, target_word_count)
    polished_word_count = count_words(polished_text)
    estimated_polished_duration_sec = estimate_speech_duration_sec(
        polished_text, resolved_target_wpm
    )

    scene_title_zh: str | None = None
    if structured:
        if _title_ok(parsed_title):
            scene_title_zh = parsed_title.strip()
        else:
            t_title0 = time.perf_counter()
            title_result = gateway_polish_text(
                messages=[
                    {
                        "role": "system",
                        "content": build_title_only_system_message(),
                    },
                    {
                        "role": "user",
                        "content": build_title_only_user_message(
                            polished_english=polished_text,
                            segment_duration_sec=float(duration_sec),
                        ),
                    },
                ],
                settings=settings,
                client_factory=client_factory,
            )
            t_title1 = time.perf_counter()
            timing_api_sec += t_title1 - t_title0
            tline = _sanitize_scene_title_line(title_result.text)
            scene_title_zh = tline if _title_ok(tline) else (tline[:10] if tline else None)

    return NarrationPolishResult(
        original_text=raw_text,
        polished_text=polished_text,
        segment_duration_sec=float(duration_sec),
        target_duration_sec=target_duration_sec,
        safety_margin_sec=resolved_safety_margin_sec,
        speaking_rate_wpm=resolved_target_wpm,
        target_word_count=target_word_count,
        original_word_count=original_word_count,
        polished_word_count=polished_word_count,
        estimated_original_duration_sec=estimated_original_duration_sec,
        estimated_polished_duration_sec=estimated_polished_duration_sec,
        cefr_level=resolved_cefr_level,
        strength=resolved_strength,
        provider=result.meta.provider,
        model=result.meta.model,
        timing_api_sec=timing_api_sec,
        scene_title_zh=scene_title_zh,
    )
