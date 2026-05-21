#!/usr/bin/env python3
"""
Run the full MovieTeller workflow for harrypotter_long.mp4.

Uses the current config stack:
- packaged default config
- config/local.yaml
- environment variables

Run from the repo root:

    python python/manual_tests/full_video_workflow_harrypotter_long.py

Behavior:
1. Run narration/polish first and persist text-stage JSON immediately.
2. Write a human-readable script (.manual.pipeline.script.txt) from that payload.
3. Merge extracted SRT + narrated segments into ``{stem}.final.subtitled.srt``, then remux
   ``{stem}.narration_softsubs.mp4`` with **mov_text** soft subtitles (no TTS; original audio kept).
4. When ``ENABLE_SPEECH_AND_VIDEO`` is True: TTS + full narrated video as before.

If TTS fails, the text-stage JSON is still preserved on disk.

Routing comes from the shared gateway config. If text JSON already exists, the
script skips the second visual-understanding pass and continues from speech/video.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


VIDEO_PATH = "test_artifacts/harrypotter_smoke1.mp4"
OUTPUT_ROOT = "test_artifacts/smokeFree2"
ENABLE_SPEECH_AND_VIDEO = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

#不安装多个本地包、又直接跑裸脚本**时，让解释器能找到分散在各 src 下的包
def _ensure_paths() -> None:
    root = _repo_root()
    for sub in (
        root / "python" / "movieteller_config" / "src",
        root / "python" / "pipeline_types" / "src",
        root / "python" / "media_utils" / "src",
        root / "python" / "subtitle_extraction" / "src",
        root / "python" / "subtitle_context" / "src",
        root / "python" / "video_frame_pool" / "src",
        root / "python" / "frame_source" / "src",
        root / "python" / "model_gateway" / "src",
        root / "python" / "narration" / "src",
        root / "python" / "narration_polish" / "src",
        root / "python" / "narration_speech" / "src",
        root / "python" / "narration_video" / "src",
        root / "python" / "movie_pipeline" / "src",
        root / "python" / "pipeline_transcript" / "src",
        root / "python" / "rerank" / "src",
    ):
        if sub.is_dir():
            sys.path.insert(0, str(sub))


# 如果key长度小于等于6，则直接返回，否则返回前6个字符加上...
def _key_preview(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 6:
        return value
    return f"{value[:6]}..."

# 打印运行时调试信息
def _print_runtime_debug(settings) -> None:
    print(
        json.dumps(
            {
                "debug": {
                    "cwd": str(Path.cwd()),
                    "repoRoot": str(_repo_root()),
                    "env": {
                        "NEW_API_KEY_NARRATION_FREE_present": bool(os.environ.get("NEW_API_KEY_NARRATION_FREE")),
                        "TTS_API_KEY_present": bool(os.environ.get("TTS_API_KEY")),
                    },
                    "gateway": {
                        "defaultProvider": settings.default_provider(),
                        "ttsProvider": settings.provider_for_capability("tts"),
                    },
                    "apiProviders": dict(settings.api_providers),
                    "apiKeys": {
                        "newapi": _key_preview(settings.get_api_key("newapi")),
                        "dashscope": _key_preview(settings.get_api_key("dashscope")),
                    },
                    "modelDefaults": dict(settings.model_defaults),
                    "ttsVoice": settings.narration_speech_options().voice,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )

# 
def _write_readable_script_from_payload(
    payload: dict[str, object],
    output_path: Path,
    *,
    source_path: Path,
) -> None:
    """Write plain-text script (subtitle context + narration) via pipeline_transcript."""
    from pipeline_transcript import build_readable_script

    if not isinstance(payload.get("narratedSegments"), list) or not payload["narratedSegments"]:
        return
    body = build_readable_script(payload, source_path=source_path)
    output_path.write_text(body, encoding="utf-8")

# 试图找到已经存在的payload，如果存在则直接返回，否则运行全流程
# 返回的内容包含narratedSegments，narratedSegments是一个列表，列表中每个元素是一个字典，字典中包含startSec, endSec, speechText, polish等字段
def _load_existing_payload(text_json_path: Path) -> dict[str, object] | None:
    if not text_json_path.is_file():
        return None
    from movie_pipeline import parse_pipeline_text_json_path

    return dict(parse_pipeline_text_json_path(text_json_path))


def _build_text_stage_context(*, video_path: Path, output_root: Path, settings):
    from movie_pipeline import WorkflowRequest, resolved_run_context_from_request

    request = WorkflowRequest(
        video_path=str(video_path),
        output_root=str(output_root),
        enable_subtitle_context=True,
        enable_polish=settings.narration_polish_enabled,
        enable_speech=False,
        enable_embed_video=False,
    )
    return resolved_run_context_from_request(
        request=request,
        settings=settings,
    )


def main() -> int:
    _ensure_paths()

    from movie_pipeline.full_workflow import run_full_workflow
    from movie_pipeline.payload_schema import (
        serialize_pipeline_render_payload,
        serialize_pipeline_speech_payload,
        serialize_pipeline_text_payload,
    )
    from movie_pipeline.subtitle_merge_stage import merge_subtitles_for_narration
    from movie_pipeline.workflow_continue import (
        render_video_from_narration_payload,
        synthesize_speech_from_text_payload,
    )
    from movieteller_config import load_settings

    root = _repo_root()
    video_path = (root / VIDEO_PATH).resolve()
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        return 1

    output_root = (root / OUTPUT_ROOT).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    settings = load_settings(require_narration=True)
    _print_runtime_debug(settings)

# 获取视频文件名，用于生成文件名
    stem = video_path.stem
    text_json_path = output_root / f"{stem}.manual.pipeline.text.json"
    text_stage_context = _build_text_stage_context(
        video_path=video_path,
        output_root=output_root,
        settings=settings,
    )
    # 文本阶段如果已有结果，就直接复用；否则从 resolved_context 继续执行
    text_payload = _load_existing_payload(text_json_path) 
    if text_payload is None:
        text_payload = run_full_workflow(
            resolved_context=text_stage_context,
        )
        text_json_path.write_text(
            serialize_pipeline_text_payload(text_payload),
            encoding="utf-8",
        )

    text_script_path = output_root / f"{stem}.manual.pipeline.script.txt"
    # 测试流程的函数
    _write_readable_script_from_payload(
        text_payload,
        text_script_path,
        source_path=text_json_path,
    )

    if not ENABLE_SPEECH_AND_VIDEO:
        softsubs_video_path = output_root / f"{stem}.narration_softsubs.mp4" # 嵌入软字幕的视频路径
        final_srt_path = output_root / f"{stem}.final.subtitled.srt"         # 合并完成后的字幕文件
        source_srt_path = output_root / f"{stem}.extracted.srt"
        subtitle_merge: dict[str, object] | None = None
        softsubs_error: str | None = None
        try:
            from narration_video import render_video_with_soft_subtitles

            if not source_srt_path.is_file():
                raise FileNotFoundError(f"Missing extracted subtitles: {source_srt_path}")
            subtitle_result = merge_subtitles_for_narration( # 合并字幕
                speech_video_json_path=str(text_json_path),
                source_srt_path=str(source_srt_path),
                output_srt_path=str(final_srt_path),
            )
            subtitle_merge = {  # 合并字幕的结果
                "sourceSrtPath": subtitle_result.source_srt_path,
                "speechVideoJsonPath": subtitle_result.speech_video_json_path,
                "outputSrtPath": subtitle_result.output_srt_path,
                "insertedCueCount": subtitle_result.inserted_cue_count,
                "totalCueCount": subtitle_result.total_cue_count,
            }
            render_video_with_soft_subtitles( # 将字幕文件进行软嵌入
                str(video_path),
                subtitle_srt_path=str(final_srt_path),
                output_path=str(softsubs_video_path),
                settings=settings,
            )
        except Exception as exc:
            softsubs_error = str(exc)

        summary: dict[str, object] = { # 总结信息，这个字典包含了视频路径、输出根目录、文本JSON路径、文本脚本路径、narratedSegments、speechAttempted、extractedSrtPath、finalSubtitledSrtPath、softSubsVideoPath等信息
            "video": str(video_path),
            "outputRoot": str(output_root),
            "textJsonPath": str(text_json_path),
            "textScriptPath": str(text_script_path),
            "narratedSegments": len(text_payload.get("narratedSegments", [])),
            "speechAttempted": False,
            "extractedSrtPath": str(source_srt_path),
            "finalSubtitledSrtPath": str(final_srt_path),
            "softSubsVideoPath": str(softsubs_video_path),
        }
        if subtitle_merge is not None:
            summary["subtitleMerge"] = subtitle_merge
        if softsubs_error is not None:
            summary["softSubsError"] = softsubs_error
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    try: # 另一条路线：合成音频到视频中
        speech_payload = synthesize_speech_from_text_payload( # 文生音频，指定音频输出路径
            payload=dict(text_payload),
            audio_output_dir=output_root / f"{stem}.narration_audio",
            settings=settings,
        )
        speech_json_path = output_root / f"{stem}.manual.pipeline.speech.json"
        speech_json_path.write_text(  # 将音频合成结果写入JSON文件
            serialize_pipeline_speech_payload(speech_payload),
            encoding="utf-8",
        )
        source_srt_path = output_root / f"{stem}.extracted.srt"  # 提取的字幕文件路径
        final_srt_path = output_root / f"{stem}.final.subtitled.srt" # 合并完成后的字幕文件路径
        subtitle_result = merge_subtitles_for_narration( # 软字幕嵌入
            speech_video_json_path=str(speech_json_path),
            source_srt_path=str(source_srt_path),
            output_srt_path=str(final_srt_path),
        )
        speech_payload["subtitleMerge"] = { # 合并字幕的结果
            "sourceSrtPath": subtitle_result.source_srt_path,
            "speechVideoJsonPath": subtitle_result.speech_video_json_path,
            "outputSrtPath": subtitle_result.output_srt_path,
            "insertedCueCount": subtitle_result.inserted_cue_count,
            "totalCueCount": subtitle_result.total_cue_count,
        }
        final_payload = render_video_from_narration_payload( # 将音频文件渲染进入视频合成解说声道视频
            payload=speech_payload,
            video_path=video_path,
            output_path=output_root / f"{stem}.narrated.mp4",
            subtitle_srt_path=final_srt_path,
            settings=settings,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "video": str(video_path),
                    "outputRoot": str(output_root),
                    "textJsonPath": str(text_json_path),
                    "textScriptPath": str(text_script_path),
                    "narratedSegments": len(text_payload.get("narratedSegments", [])),
                    "speechAttempted": True,
                    "speechSucceeded": False,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    render_json_path = output_root / f"{stem}.manual.pipeline.render.json"
    render_json_path.write_text(
        serialize_pipeline_render_payload(final_payload),
        encoding="utf-8",
    )
    speech_video_script_path = output_root / f"{stem}.manual.pipeline.render.script.txt"
    _write_readable_script_from_payload(
        final_payload,
        speech_video_script_path,
        source_path=render_json_path,
    )

    print(
        json.dumps(
            {
                "video": str(video_path),
                "outputRoot": str(output_root),
                "textJsonPath": str(text_json_path),
                "textScriptPath": str(text_script_path),
                "speechJsonPath": str(speech_json_path),
                "renderJsonPath": str(render_json_path),
                "renderScriptPath": str(speech_video_script_path),
                "audioDir": str(output_root / f"{stem}.narration_audio"),
                "videoOutput": str(output_root / f"{stem}.narrated.mp4"),
                "narratedSegments": len(final_payload.get("narratedSegments", [])),
                "speechAttempted": True,
                "speechSucceeded": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
