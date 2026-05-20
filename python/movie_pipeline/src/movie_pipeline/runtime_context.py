"""Immutable per-run context: resolved Settings plus pipeline runtime options.

Use :func:`run_pipeline_ctx` instead of passing ``settings`` and
``pipeline`` config separately through orchestration boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from movieteller_config.schema import Settings

from movie_pipeline.types import NarrationPipelineConfig

'''
1. settings: Settings —— 全局、已解析的运行配置
大致有哪些数据（归类，不逐字段背）：

密钥与网关：api_keys、api_providers、gateway_default_provider、gateway_tts_provider、model_catalog、model_defaults 等。
工具路径与媒体默认值：ffmpeg_path、videocaptioner_*、帧池相关数值（max_frames_per_segment、narration_frame_max_edge、pool_*、dialogue_overlap_threshold、pyscenedetect_merge_sec 等）。
叙述/润色/TTS/成片的默认倾向：narration_polish_enabled、narration_tts_enabled、润色目标语速/CEFR/强度、tts_default_*、成片音量等。
本仓库与帧池强相关：frame_pool_manifest（本趟若建了帧池，常被改成当前 manifest 路径）。
作用：
一次 run 里「从配置文件/环境读出来并已合并」的全局真相源；pipeline 里调模型、调 ffmpeg、帧池、字幕上下文索引等，多数从 ctx.settings 取默认值或凭证。它和「这一条视频单独改 gap」那种东西分开，避免把全局配置塞进 NarrationPipelineConfig。

2. pipeline: NarrationPipelineConfig —— 本趟叙述流水线的参数
作用：
只服务 **run_pipeline_ctx 这条「图生文 → 可选润色 → 可选 TTS → 可选嵌视频」**路径：分析字幕用 min_gap_sec / ffprobe_bin；叙述用 narration_options、frame_source_options、RAG 检索选项；是否润色/合成/成片由 polish_options / speech_* / embed_* / video_options 等是否为 None 或路径决定。
这是 per-run、和当前视频/输出目录绑得最紧 的那一层。

'''

@dataclass(frozen=True)
class RunContext:
    """Single bag for one pipeline execution (global config + per-run options)."""

    settings: Settings
    pipeline: NarrationPipelineConfig

    def with_settings(self, settings: Settings) -> RunContext:
        """Return a new context with replaced Settings (e.g. per-run ``frame_pool_manifest``)."""
        return replace(self, settings=settings)
