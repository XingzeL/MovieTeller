from __future__ import annotations

import argparse
import json
from pathlib import Path

from frame_source import FrameSourceOptions
from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict

from movie_pipeline.pipeline import run_pipeline_ctx
from movie_pipeline.payload_schema import (
    serialize_pipeline_render_payload,
    serialize_pipeline_text_payload,
)
from movie_pipeline.runtime_context import RunContext
from movie_pipeline.types import NarrationPipelineConfig
from movie_pipeline.workflow_continue import render_video_from_narration_payload


def _resolve_cli_settings(args):
    if (
        args.frame_pool_manifest is None
    ):
        return load_settings(require_narration=True)
    flat = load_flat_dict()
    if args.frame_pool_manifest is not None:
        flat["frame_pool_manifest"] = args.frame_pool_manifest.strip()
    settings = settings_from_dict(flat)
    settings.require_api_key(settings.default_provider())
    return settings


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Run the MovieTeller narration pipeline from subtitle analysis through optional render."
    )
    ap.add_argument("--srt", required=True, help="Path to extracted .srt file")
    ap.add_argument("--video", required=True, help="Source video path")
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
        help="Reserved compatibility flag. Pipeline always narrates derived candidates.",
    )
    ap.add_argument(
        "--prompt-style",
        default=None,
        help="Prompt style for narration (default: movieteller_config default_prompt_style)",
    )
    ap.add_argument("--custom-prompt", default="", help="Extra instructions for narration")
    ap.add_argument(
        "--frame-pool-manifest",
        default=None,
        help="Optional frame-pool manifest path override for narration",
    )
    ap.add_argument(
        "--subtitle-context-index-dir",
        default=None,
        help="Optional subtitle context index dir; defaults to sibling <srt>.subtitle_context when present",
    )
    ap.add_argument(
        "--build-subtitle-context",
        action="store_true",
        help="Build subtitle context index before narration if it does not already exist",
    )
    ap.add_argument(
        "--subtitle-context-history-window-sec",
        type=float,
        default=None,
        help="Only retrieve subtitle context this many seconds before the current segment",
    )
    ap.add_argument(
        "--subtitle-context-top-k",
        type=int,
        default=None,
        help="How many subtitle context chunks to retrieve",
    )
    ap.add_argument(
        "--subtitle-context-chunk-cue-count",
        type=int,
        default=None,
        help="How many subtitle cues each context chunk contains when building the index",
    )
    ap.add_argument(
        "--subtitle-context-chunk-stride",
        type=int,
        default=None,
        help="Stride between subtitle context chunks when building the index",
    )
    ap.add_argument(
        "--polish",
        action="store_true",
        help="Rewrite narration to better fit TTS duration constraints",
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
        "--speech-voice", default=None, help="Override TTS voice")
    ap.add_argument("--speech-rate", default=None, help="Override TTS rate, e.g. +5%%")
    ap.add_argument("--speech-volume", default=None, help="Override TTS volume, e.g. +0%%")
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
    return ap


def main() -> int:
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "export-study-html":
        from movie_pipeline.study_cards_html import main as export_study_main

        return export_study_main(argv[1:])

    ap = build_parser()
    args = ap.parse_args()

    settings = _resolve_cli_settings(args)
    narration_options = settings.narration_options(
        prompt_style=args.prompt_style,
        custom_prompt=args.custom_prompt,
    )
    speech_enabled = bool(args.embed_video) or bool(args.speech)
    speech_output_dir = args.speech_output_dir
    if speech_enabled and not (speech_output_dir or "").strip():
        speech_output_dir = str(Path(args.video).resolve().with_suffix("")) + ".narration_audio"
    embed_output_path = args.embed_output
    if args.embed_video and not (embed_output_path or "").strip():
        embed_output_path = str(Path(args.video).resolve().with_suffix("")) + ".narrated.mp4"
    pipeline_config = NarrationPipelineConfig(
        video_duration_sec=args.duration_sec,
        min_gap_sec=args.min_gap_sec,
        subtitle_guard_sec=args.subtitle_guard_sec,
        ffprobe_bin=args.ffprobe_bin,
        narration_options=narration_options,
        frame_source_options=FrameSourceOptions(
            ffmpeg_bin=settings.ffmpeg_path,
            max_frames_per_segment=settings.max_frames_per_segment,
            max_edge_pixels=settings.narration_frame_max_edge,
            pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
        ),
        subtitle_context_build_options=settings.subtitle_context_build_options(
            chunk_cue_count=args.subtitle_context_chunk_cue_count,
            chunk_stride=args.subtitle_context_chunk_stride,
        ),
        subtitle_context_retrieve_options=settings.subtitle_context_retrieve_options(
            history_window_sec=args.subtitle_context_history_window_sec,
            top_k=args.subtitle_context_top_k,
        ),
        polish_options=(
            settings.narration_polish_options(
                prompt_style=narration_options.prompt_style,
                target_wpm=args.polish_target_wpm,
                cefr_level=args.polish_cefr_level,
                strength=args.polish_strength,
                safety_margin_sec=args.polish_safety_margin_sec,
            )
            if args.polish
            else None
        ),
        speech_options=(
            settings.narration_speech_options(
                voice=args.speech_voice,
                rate=args.speech_rate,
                volume=args.speech_volume,
                pitch=args.speech_pitch,
                boundary=args.speech_boundary,
            )
            if speech_enabled
            else None
        ),
        video_options=(
            settings.narration_video_options(
                background_audio_volume=args.background_audio_volume,
                speech_audio_volume=args.narration_audio_volume,
            )
            if args.embed_video
            else None
        ),
    )
    ctx = RunContext(settings=settings, pipeline=pipeline_config)
    payload = run_pipeline_ctx(
        srt_path=args.srt,
        video_path=args.video,
        ctx=ctx,
        subtitle_context_index_dir=args.subtitle_context_index_dir,
        build_subtitle_context=args.build_subtitle_context,
        speech_output_dir=speech_output_dir,
        embed_video=args.embed_video,
    )
    if args.embed_video:
        payload = render_video_from_narration_payload(
            payload=payload,
            video_path=Path(args.video),
            output_path=Path(embed_output_path),
            subtitle_srt_path=None,
            settings=settings,
        )
    rendered_video = payload.get("renderedVideo")

    if args.json:
        if rendered_video:
            print(serialize_pipeline_render_payload(payload))
        else:
            print(serialize_pipeline_text_payload(payload))
    else:
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
        if rendered_video:
            print(rendered_video["outputPath"])
    return 0
