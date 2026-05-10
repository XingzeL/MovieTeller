from __future__ import annotations

import math
import re
import time
from typing import TYPE_CHECKING, Any, Callable

from movieteller_config import load_settings

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


def _resolve_provider_slug(settings: "Settings", provider_slug: str | None) -> str:
    slug = (provider_slug or settings.polish_provider()).strip().lower()
    return slug or "openai"


def _resolve_base_url(settings: "Settings", slug: str) -> str | None:
    base_url = settings.get_api_base_url(slug)
    if slug == "openai" and not base_url:
        return settings.openai_base_url
    return base_url


def _openai_sdk_client_factory(api_key: str, base_url: str | None) -> Any:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


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
    target_wpm: int | None = None,
    cefr_level: str | None = None,
    strength: str | None = None,
    safety_margin_sec: float | None = None,
    provider_slug: str | None = None,
    model: str | None = None,
    settings: "Settings | None" = None,
    client_factory: Callable[..., Any] | None = None,
) -> NarrationPolishResult:
    raw_text = _normalize_text(text)
    if not raw_text:
        raise ValueError("narration text is empty")

    cfg = settings if settings is not None else load_settings()
    resolved_target_wpm = max(
        1,
        int(
            target_wpm
            if target_wpm is not None
            else getattr(cfg, "narration_polish_target_wpm", 150)
        ),
    )
    resolved_cefr_level = (
        str(
            cefr_level
            if cefr_level is not None
            else getattr(cfg, "narration_polish_cefr_level", "B1")
        )
        .strip()
        .upper()
        or "B1"
    )
    resolved_strength = (
        str(
            strength
            if strength is not None
            else getattr(cfg, "narration_polish_strength", "medium")
        )
        .strip()
        .lower()
        or "medium"
    )
    resolved_safety_margin_sec = max(
        0.0,
        float(
            safety_margin_sec
            if safety_margin_sec is not None
            else getattr(cfg, "narration_polish_safety_margin_sec", 0.2)
        ),
    )
    resolved_provider = _resolve_provider_slug(cfg, provider_slug)
    resolved_model = model or cfg.polish_model_for_provider(resolved_provider)
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

    api_key = cfg.require_api_key(resolved_provider)
    base_url = _resolve_base_url(cfg, resolved_provider)
    factory = client_factory or _openai_sdk_client_factory
    client = factory(api_key, base_url)

    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {
                "role": "system",
                "content": build_system_message(
                    cefr_level=resolved_cefr_level, strength=resolved_strength
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
        ],
    )
    t1 = time.perf_counter()

    content = (resp.choices[0].message.content or "").strip()
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
        provider=resolved_provider,
        model=resolved_model,
        timing_api_sec=t1 - t0,
    )
