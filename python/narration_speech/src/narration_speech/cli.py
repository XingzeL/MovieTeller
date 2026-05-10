from __future__ import annotations

import argparse
import json

from narration_speech.speech import synthesize_narration_text


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate TTS audio for MovieTeller narration using edge-tts."
    )
    ap.add_argument("--text", required=True, help="Narration text to synthesize")
    ap.add_argument(
        "--duration-sec",
        type=float,
        required=True,
        help="Original segment duration in seconds",
    )
    ap.add_argument("--output", required=True, help="Output audio path")
    ap.add_argument(
        "--target-duration-sec",
        type=float,
        default=None,
        help="Optional stricter target duration to fit inside",
    )
    ap.add_argument("--provider", default=None, help="Speech provider slug override")
    ap.add_argument("--voice", default=None, help="edge-tts voice name override")
    ap.add_argument("--rate", default=None, help="edge-tts speaking rate, e.g. +5%")
    ap.add_argument("--volume", default=None, help="edge-tts volume, e.g. +0%")
    ap.add_argument("--pitch", default=None, help="edge-tts pitch, e.g. +0Hz")
    ap.add_argument(
        "--boundary",
        default=None,
        help="Boundary metadata mode: SentenceBoundary or WordBoundary",
    )
    ap.add_argument("--metadata", default=None, help="Optional metadata jsonl output path")
    ap.add_argument("--json", action="store_true", help="Print JSON payload")
    args = ap.parse_args()

    result = synthesize_narration_text(
        args.text,
        args.duration_sec,
        output_path=args.output,
        metadata_path=args.metadata,
        target_duration_sec=args.target_duration_sec,
        provider_slug=args.provider,
        voice=args.voice,
        rate=args.rate,
        volume=args.volume,
        pitch=args.pitch,
        boundary=args.boundary,
    )
    payload = {
        "text": result.text,
        "segmentDurationSec": result.segment_duration_sec,
        "targetDurationSec": result.target_duration_sec,
        "audioPath": result.audio_path,
        "metadataPath": result.metadata_path,
        "rawDurationSec": result.raw_duration_sec,
        "audioDurationSec": result.audio_duration_sec,
        "durationDeltaSec": result.duration_delta_sec,
        "fitsDuration": result.fits_duration,
        "provider": result.provider,
        "voice": result.voice,
        "rate": result.rate,
        "volume": result.volume,
        "pitch": result.pitch,
        "boundary": result.boundary,
        "fitApplied": result.fit_applied,
        "timingTtsSec": result.timing_tts_sec,
        "timingFitSec": result.timing_fit_sec,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            f"{payload['audioPath']} duration={payload['audioDurationSec']:.3f}s "
            f"target={payload['targetDurationSec']:.3f}s fit={payload['fitApplied']}"
        )
    return 0
