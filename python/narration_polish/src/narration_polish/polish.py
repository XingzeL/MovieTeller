from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING, Any, Callable

from model_gateway import polish_text as gateway_polish_text
from movieteller_config import load_settings
from movieteller_config.schema import NarrationPolishOptions

from narration_polish.prompts import build_system_message, build_user_message
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

    content = result.text.strip()
    if not content:
        raise RuntimeError("Model returned empty polished narration text")
    polished_text = _truncate_to_word_budget(content, target_word_count)
    polished_word_count = count_words(polished_text)
    estimated_polished_duration_sec = estimate_speech_duration_sec(
        polished_text, resolved_target_wpm
    )
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
        timing_api_sec=t1 - t0,
    )
