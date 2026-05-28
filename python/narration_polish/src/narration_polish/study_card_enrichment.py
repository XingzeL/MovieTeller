from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any, Callable

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events

from model_gateway import polish_text as gateway_polish_text

from narration_polish.prompts import (
    build_vocab_highlight_system_message,
    build_vocab_highlight_user_message,
)

if TYPE_CHECKING:
    from movieteller_config.schema import Settings

_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\r?\n?(.*?)\r?\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def generate_vocab_study_card(
    passage: str,
    *,
    cefr_level: str,
    output_language: str = "en",
    settings: "Settings",
    client_factory: Callable[..., Any] | None = None,
) -> tuple[dict[str, Any] | None, float]:
    text = str(passage or "").strip()
    if not text:
        return None, 0.0
    emit_event(
        log_events.STUDY_CARD_START,
        capability="study_enrichment",
        passage_chars=len(text),
        status="ok",
    )
    start = time.perf_counter()
    try:
        result = gateway_polish_text(
            messages=[
                {
                    "role": "system",
                    "content": build_vocab_highlight_system_message(output_language),
                },
                {
                    "role": "user",
                    "content": build_vocab_highlight_user_message(
                        passage=text,
                        cefr_level=cefr_level,
                        output_language=output_language,
                    ),
                },
            ],
            settings=settings,
            client_factory=client_factory,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        emit_event(
            log_events.STUDY_CARD_FAILED,
            level=logging.ERROR,
            capability="study_enrichment",
            passage_chars=len(text),
            duration_ms=int(elapsed * 1000),
            status="error",
            fatal=False,
            **classify_error(exc),
        )
        raise
    elapsed = time.perf_counter() - start
    parsed = parse_vocab_study_card_json(result.text)
    emit_event(
        log_events.STUDY_CARD_DONE,
        capability="study_enrichment",
        passage_chars=len(text),
        duration_ms=int(elapsed * 1000),
        status="ok",
    )
    return parsed, elapsed


def parse_vocab_study_card_json(raw: str) -> dict[str, Any] | None:
    try:
        text = _strip_optional_json_fence(str(raw or "").strip())
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    data = obj.get("data")
    if not isinstance(data, list):
        return None
    cleaned: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        match_text = item.get("match_text")
        if not isinstance(match_text, str) or not match_text.strip():
            continue
        cleaned.append(item)
    out: dict[str, Any] = dict(obj)
    out["data"] = cleaned
    if not isinstance(out.get("full_translation"), str):
        out["full_translation"] = str(out.get("full_translation") or "")
    if not isinstance(out.get("passage_id"), str):
        out["passage_id"] = str(out.get("passage_id") or "seg")
    try:
        out["highlights_count"] = int(out.get("highlights_count", len(cleaned)))
    except (TypeError, ValueError):
        out["highlights_count"] = len(cleaned)
    return out


def _strip_optional_json_fence(raw: str) -> str:
    match = _JSON_FENCE_RE.match(raw.strip())
    if match:
        return match.group(1).strip()
    return raw.strip()
