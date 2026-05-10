from __future__ import annotations

import argparse
import json

from subtitle_analysis.analyze import analyze_subtitle_file, result_to_dict


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Analyze SRT subtitle coverage and derive no-subtitle narration candidates."
    )
    ap.add_argument("--srt", required=True, help="Path to extracted .srt file")
    ap.add_argument("--video", default=None, help="Optional media path for probing full duration")
    ap.add_argument(
        "--duration-sec",
        type=float,
        default=None,
        help="Optional explicit full video duration in seconds",
    )
    ap.add_argument(
        "--min-gap-sec",
        type=float,
        default=1.0,
        help="Minimum gap duration after trimming to keep as narration candidate",
    )
    ap.add_argument(
        "--subtitle-guard-sec",
        type=float,
        default=0.25,
        help="Trim this many seconds away from subtitle boundaries",
    )
    ap.add_argument("--ffprobe-bin", default="ffprobe", help="ffprobe executable path")
    ap.add_argument(
        "--narrate",
        action="store_true",
        help="Run narration on derived no-subtitle candidates and include timed narration JSON",
    )
    ap.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Limit how many narration candidates are sent to narration",
    )
    ap.add_argument(
        "--prompt-style",
        default=None,
        help="Prompt style for narration (default: movieteller_config default_prompt_style)",
    )
    ap.add_argument("--custom-prompt", default="", help="Extra instructions for narration")
    ap.add_argument("--model", default=None, help="Override narration model id")
    ap.add_argument(
        "--provider",
        default=None,
        help="Override narration provider slug for the pipeline run",
    )
    ap.add_argument(
        "--polish",
        action="store_true",
        help="Rewrite narration to better fit TTS duration constraints",
    )
    ap.add_argument(
        "--polish-provider",
        default=None,
        help="Override narration polish provider slug for the pipeline run",
    )
    ap.add_argument(
        "--polish-model",
        default=None,
        help="Override narration polish model id",
    )
    ap.add_argument(
        "--polish-model-index",
        type=int,
        default=None,
        help="Override narration polish model catalog index when --polish-model is unset",
    )
    ap.add_argument(
        "--polish-target-wpm",
        type=int,
        default=None,
        help="Target speaking rate for narration polishing",
    )
    ap.add_argument(
        "--polish-cefr-level",
        default=None,
        help="Requested CEFR level for polished narration (e.g. A1, B1, C1)",
    )
    ap.add_argument(
        "--polish-strength",
        default=None,
        help="Rewrite strength for narration polishing (light, medium, strong)",
    )
    ap.add_argument(
        "--polish-safety-margin-sec",
        type=float,
        default=None,
        help="Reserve this much time inside the segment when polishing for TTS",
    )
    ap.add_argument(
        "--speech",
        action="store_true",
        help="Synthesize speech audio for each narration segment",
    )
    ap.add_argument(
        "--speech-provider",
        default=None,
        help="Override narration speech provider slug for the pipeline run",
    )
    ap.add_argument("--speech-voice", default=None, help="Override TTS voice")
    ap.add_argument("--speech-rate", default=None, help="Override TTS rate, e.g. +5%")
    ap.add_argument("--speech-volume", default=None, help="Override TTS volume, e.g. +0%")
    ap.add_argument("--speech-pitch", default=None, help="Override TTS pitch, e.g. +0Hz")
    ap.add_argument(
        "--speech-boundary",
        default=None,
        help="Boundary metadata mode: SentenceBoundary or WordBoundary",
    )
    ap.add_argument(
        "--speech-output-dir",
        default=None,
        help="Directory for synthesized narration audio files",
    )
    ap.add_argument(
        "--embed-video",
        action="store_true",
        help="Mix synthesized narration audio back into the source video",
    )
    ap.add_argument(
        "--embed-output",
        default=None,
        help="Rendered output video path when --embed-video is set",
    )
    ap.add_argument(
        "--background-audio-volume",
        type=float,
        default=None,
        help="Volume multiplier for original video audio during embed",
    )
    ap.add_argument(
        "--narration-audio-volume",
        type=float,
        default=None,
        help="Volume multiplier for synthesized narration audio during embed",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON payload")
    args = ap.parse_args()

    if args.narrate:
        from subtitle_analysis.pipeline import analyze_and_narrate

        if not args.video:
            ap.error("--video is required when --narrate is set")
        payload = analyze_and_narrate(
            srt_path=args.srt,
            video_path=args.video,
            video_duration_sec=args.duration_sec,
            min_gap_sec=args.min_gap_sec,
            subtitle_guard_sec=args.subtitle_guard_sec,
            ffprobe_bin=args.ffprobe_bin,
            max_candidates=args.max_candidates,
            prompt_style=args.prompt_style,
            custom_prompt=args.custom_prompt,
            image_model=args.model,
            provider_slug=args.provider,
            polish=args.polish if args.polish else None,
            polish_provider_slug=args.polish_provider,
            polish_model=args.polish_model,
            polish_model_index=args.polish_model_index,
            polish_target_wpm=args.polish_target_wpm,
            polish_cefr_level=args.polish_cefr_level,
            polish_strength=args.polish_strength,
            polish_safety_margin_sec=args.polish_safety_margin_sec,
            speech=(True if args.embed_video else (args.speech if args.speech else None)),
            speech_provider_slug=args.speech_provider,
            speech_voice=args.speech_voice,
            speech_rate=args.speech_rate,
            speech_volume=args.speech_volume,
            speech_pitch=args.speech_pitch,
            speech_boundary=args.speech_boundary,
            speech_output_dir=args.speech_output_dir,
            embed_video=args.embed_video,
            embed_output_path=args.embed_output,
            background_audio_volume=args.background_audio_volume,
            narration_audio_volume=args.narration_audio_volume,
        )
    else:
        if args.polish or args.speech or args.embed_video:
            ap.error("--polish, --speech, and --embed-video require --narrate")
        result = analyze_subtitle_file(
            args.srt,
            video_path=args.video,
            video_duration_sec=args.duration_sec,
            min_gap_sec=args.min_gap_sec,
            subtitle_guard_sec=args.subtitle_guard_sec,
            ffprobe_bin=args.ffprobe_bin,
        )
        payload = result_to_dict(result)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if args.narrate:
            print(
                f"subtitle_spans={len(payload['subtitleSpans'])} "
                f"raw_gaps={len(payload['rawGaps'])} "
                f"narration_candidates={len(payload['narrationCandidates'])} "
                f"narrated_segments={len(payload['narratedSegments'])}"
            )
            for seg in payload["narratedSegments"]:
                line_text = seg.get("speechText") or seg["text"]
                print(
                    f"{seg['startSec']:.3f}-{seg['endSec']:.3f}s "
                    f"({seg['durationSec']:.3f}s) {line_text}"
                )
            if payload.get("renderedVideo"):
                print(payload["renderedVideo"]["outputPath"])
        else:
            print(
                f"subtitle_spans={len(payload['subtitleSpans'])} "
                f"raw_gaps={len(payload['rawGaps'])} "
                f"narration_candidates={len(payload['narrationCandidates'])}"
            )
            for seg in payload["narrationCandidates"]:
                print(
                    f"{seg['startSec']:.3f}-{seg['endSec']:.3f}s "
                    f"({seg['durationSec']:.3f}s)"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
