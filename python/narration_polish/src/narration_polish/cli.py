from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict

from narration_polish.polish import polish_narration_text


def _resolve_cli_settings(
    provider_override: str | None,
    model_override: str | None,
    model_index_override: int | None,
    target_wpm_override: int | None,
    cefr_level_override: str | None,
    strength_override: str | None,
    safety_margin_sec_override: float | None,
):
    if (
        provider_override is None
        and model_override is None
        and model_index_override is None
        and target_wpm_override is None
        and cefr_level_override is None
        and strength_override is None
        and safety_margin_sec_override is None
    ):
        settings = load_settings()
    else:
        flat = load_flat_dict()
        if provider_override is not None:
            flat["narration_polish_provider"] = provider_override.strip().lower()
        if model_override is not None:
            flat["narration_polish_model"] = model_override.strip()
        if model_index_override is not None:
            flat["narration_polish_model_index"] = int(model_index_override)
        if target_wpm_override is not None:
            flat["narration_polish_target_wpm"] = int(target_wpm_override)
        if cefr_level_override is not None:
            flat["narration_polish_cefr_level"] = cefr_level_override.strip().upper()
        if strength_override is not None:
            flat["narration_polish_strength"] = strength_override.strip().lower()
        if safety_margin_sec_override is not None:
            flat["narration_polish_safety_margin_sec"] = float(safety_margin_sec_override)
        settings = settings_from_dict(flat)
    settings.require_api_key(settings.polish_provider())
    return settings


def _read_text(text: str | None, text_file: str | None) -> str:
    if text is not None:
        return text.strip()
    if text_file is not None:
        return Path(text_file).read_text(encoding="utf-8").strip()
    raise ValueError("either --text or --text-file is required")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m narration_polish",
        description="Rewrite narration text so later TTS is more likely to fit the segment duration.",
    )
    p.add_argument("--text", default=None, help="Raw narration text")
    p.add_argument("--text-file", default=None, help="Read raw narration text from a file")
    p.add_argument(
        "--duration-sec",
        required=True,
        type=float,
        help="Segment duration in seconds",
    )
    p.add_argument("--provider", default=None, help="Override polish provider slug")
    p.add_argument("--model", default=None, help="Override polish model id")
    p.add_argument(
        "--style",
        default=None,
        help="Narration style hint to preserve during polish (e.g. documentary, movie_commentary)",
    )
    p.add_argument(
        "--model-index",
        type=int,
        default=None,
        help="Override polish model catalog index when --model is unset",
    )
    p.add_argument("--target-wpm", type=int, default=None, help="Target speaking rate")
    p.add_argument(
        "--cefr-level",
        default=None,
        help="Requested CEFR level (e.g. A1, B1, C1)",
    )
    p.add_argument(
        "--strength",
        default=None,
        help="Rewrite strength: light, medium, or strong",
    )
    p.add_argument(
        "--safety-margin-sec",
        type=float,
        default=None,
        help="Reserve this much time inside the segment",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Print JSON instead of plain text",
    )
    args = p.parse_args(argv)

    try:
        raw_text = _read_text(args.text, args.text_file)
        settings = _resolve_cli_settings(
            args.provider,
            args.model,
            args.model_index,
            args.target_wpm,
            args.cefr_level,
            args.strength,
            args.safety_margin_sec,
        )
        options = settings.narration_polish_options(
            provider_slug=args.provider,
            model=args.model,
            prompt_style=args.style,
            target_wpm=args.target_wpm,
            cefr_level=args.cefr_level,
            strength=args.strength,
            safety_margin_sec=args.safety_margin_sec,
        )
        result = polish_narration_text(
            raw_text,
            args.duration_sec,
            options=options,
            settings=settings,
        )
    except Exception as e:
        msg = str(e) or e.__class__.__name__
        if args.json_out:
            print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stdout)
        else:
            print(msg, file=sys.stderr)
        return 1

    if args.json_out:
        out: dict[str, Any] = {
            "originalText": result.original_text,
            "polishedText": result.polished_text,
            "segmentDurationSec": result.segment_duration_sec,
            "targetDurationSec": result.target_duration_sec,
            "safetyMarginSec": result.safety_margin_sec,
            "speakingRateWpm": result.speaking_rate_wpm,
            "targetWordCount": result.target_word_count,
            "originalWordCount": result.original_word_count,
            "polishedWordCount": result.polished_word_count,
            "estimatedOriginalDurationSec": result.estimated_original_duration_sec,
            "estimatedPolishedDurationSec": result.estimated_polished_duration_sec,
            "cefrLevel": result.cefr_level,
            "strength": result.strength,
            "provider": result.provider,
            "model": result.model,
            "fitsDuration": result.fits_duration,
            "timingApiSec": result.timing_api_sec,
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(result.polished_text)
    return 0
