from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict

from narration.narrate import narrate_segment_with_duration


def _resolve_cli_settings(
    provider_override: str | None,
    frame_pool_manifest_override: str | None,
):
    """Apply optional ``--provider`` without mutating frozen Settings in place."""
    if provider_override is None and frame_pool_manifest_override is None:
        return load_settings(require_narration=True)
    flat = load_flat_dict()
    if provider_override is not None:
        flat["narration_provider"] = provider_override.strip().lower()
    if frame_pool_manifest_override is not None:
        flat["frame_pool_manifest"] = frame_pool_manifest_override.strip()
    s = settings_from_dict(flat)
    s.require_api_key(s.narration_provider)
    return s


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m narration",
        description="Generate narration for a video segment (ffmpeg + OpenAI-compatible vision API).",
    )
    p.add_argument("--video", required=True, help="Path to local video file")
    p.add_argument("--start", type=float, default=None, help="Segment start (seconds)")
    p.add_argument("--end", type=float, default=None, help="Segment end (seconds)")
    p.add_argument(
        "--prompt-style",
        default=None,
        help="Prompt style (default: from movieteller_config default_prompt_style)",
    )
    p.add_argument("--custom-prompt", default="", help="Extra instructions appended to system")
    p.add_argument("--model", default=None, help="Override vision/chat model id")
    p.add_argument(
        "--provider",
        default=None,
        help="Override narration_provider slug (e.g. openai, modelscope); default from config",
    )
    p.add_argument(
        "--frame-pool-manifest",
        default=None,
        help="Optional frame-pool manifest path override",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Print JSON object with text and duration_sec on stdout",
    )
    args = p.parse_args(argv)

    settings = _resolve_cli_settings(args.provider, args.frame_pool_manifest)
    narration_options = settings.narration_options(
        provider_slug=args.provider,
        model=args.model,
        prompt_style=args.prompt_style,
        custom_prompt=args.custom_prompt,
    )

    try:
        text, duration_sec = narrate_segment_with_duration(
            args.video,
            args.start,
            args.end,
            options=narration_options,
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
        out: dict[str, Any] = {"text": text, "duration_sec": duration_sec}
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(text)
    return 0
