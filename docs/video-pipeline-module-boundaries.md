# MovieTeller Video Pipeline Module Boundaries

## Goal

这份文档定义视频处理链的目标模块边界、核心接口以及模块之间应保留的数据耦合关系。

目标：

1. `subtitle_analysis` 只做字幕分析，不再负责总流程编排
2. `narration` 只消费帧和文本上下文，不直接查 `video_frame_pool`
3. 业务模块之间通过稳定 DTO 或文件产物连接
4. 真正的调用顺序只放在单独的 orchestration 层
5. 配置在入口集中加载，再显式传给各模块

---

## Problems In Current Structure

当前仓库中存在几类不理想的耦合：

- `subtitle_analysis` 同时承担“分析”和“流水线编排”
- `narration` 同时承担“旁白生成”和“上游取帧/取字幕上下文”
- `narration_speech`、`narration_video` 依赖 `narration` 中的媒体工具函数
- 多个模块内部直接 `load_settings()`，形成隐藏的全局配置耦合
- `subtitle_context`、`video_frame_pool` 直接依赖 `subtitle_extraction` 的解析实现

目标不是完全消灭耦合，而是把耦合收敛为：

- 稳定的数据耦合
- 明确的文件耦合
- 单一的 orchestration 控制耦合

---

## Layering

建议拆成三层。

### 1. Shared Foundation

- `movieteller_config`
- `rerank`
- `media_utils`
- `subtitle_schema` 或 `subtitle_io`

### 2. Domain Capability Modules

- `subtitle_extraction`
- `subtitle_analysis`
- `subtitle_context`
- `video_frame_pool`
- `frame_source`
- `narration`
- `narration_polish`
- `narration_speech`
- `narration_video`

### 3. Orchestration

- `movie_pipeline`

原则：

- 领域模块尽量不直接调用其他领域模块
- orchestration 层负责控制顺序

---

## Core DTOs

模块之间应优先通过以下稳定数据结构连接。

### SubtitleCue

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    start_sec: float
    end_sec: float
    text: str
```

### NarrationCandidate

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationCandidate:
    start_sec: float
    end_sec: float
    prev_subtitle_text: str | None
    next_subtitle_text: str | None
```

### FrameBatch

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FrameBatch:
    frames_base64_png: tuple[str, ...]
    frame_times_sec: tuple[float, ...]
    duration_sec: float
    source: Literal["uniform", "frame_pool", "external"]
    shot_ids: tuple[int, ...] | None = None
```

### NarrationContext

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationContext:
    segment_start_sec: float
    segment_end_sec: float
    prev_subtitle_text: str | None = None
    next_subtitle_text: str | None = None
    retrieved_context_texts: tuple[str, ...] = ()
```

### NarrationResult

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationResult:
    text: str
    duration_sec: float
    frame_count: int
    frame_source: str
    timing_extract_sec: float | None = None
    timing_api_sec: float | None = None
    timing_total_sec: float | None = None
```

### NarrationAudioSegment

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NarrationAudioSegment:
    start_sec: float
    end_sec: float
    audio_path: str
```

这些 DTO 才是跨模块边界的核心契约。

---

## Module Responsibilities And Interfaces

## subtitle_extraction

职责：

- 从视频提取字幕
- 解析 `.srt`

建议接口：

```python
def extract_subtitles(
    video_path: str,
    *,
    output_srt_path: str | None = None,
    options: SubtitleExtractionOptions,
) -> ExtractionResult:
    ...
```

```python
def parse_srt_text(raw: str) -> list[SubtitleCue]:
    ...
```

输出：

- 文件：`.srt`
- 内存：`list[SubtitleCue]`

---

## subtitle_analysis

职责：

- 分析字幕覆盖区间
- 计算无字幕候选旁白区间

建议接口：

```python
def analyze_subtitle_cues(
    cues: list[SubtitleCue],
    *,
    video_duration_sec: float | None = None,
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
) -> SubtitleAnalysisResult:
    ...
```

```python
def analyze_subtitle_file(
    srt_path: str,
    *,
    video_duration_sec: float | None = None,
    video_path: str | None = None,
    ffprobe_bin: str = "ffprobe",
    min_gap_sec: float = 1.0,
    subtitle_guard_sec: float = 0.25,
) -> SubtitleAnalysisResult:
    ...
```

输出：

- `SubtitleAnalysisResult`
- `NarrationCandidate[]`

约束：

- 不直接调用 `narration`
- 不直接调用 `narration_polish`
- 不直接调用 `narration_speech`
- 不直接调用 `narration_video`

---

## subtitle_context

职责：

- 基于字幕建立本地向量索引
- 只检索目标时间点之前的历史字幕
- 用 MMR 做去重复重排

建议接口：

```python
def build_subtitle_context_index(
    *,
    cues: list[SubtitleCue] | None = None,
    srt_path: str | None = None,
    output_dir: str,
    options: SubtitleContextBuildOptions,
) -> SubtitleContextBuildResult:
    ...
```

```python
def retrieve_past_subtitle_context(
    *,
    index_dir: str,
    query_text: str,
    segment_start_sec: float,
    options: SubtitleContextRetrieveOptions,
) -> SubtitleContextRetrievalResult:
    ...
```

输出：

- 文件：`chunks.jsonl`, `embeddings.npy`, `build_config.json`
- 内存：`RetrievedSubtitleContextChunk[]`

---

## video_frame_pool

职责：

- 预处理视频并建立帧池
- 按 shot 和字幕覆盖关系构建候选帧
- 为某个时间段返回标准化帧结果

建议接口：

```python
def build_frame_pool(
    *,
    video_path: str,
    cues: list[SubtitleCue] | None = None,
    srt_path: str | None = None,
    output_dir: str,
    options: FramePoolBuildOptions,
) -> FramePoolBuildResult:
    ...
```

```python
def query_frame_pool_as_frame_batch(
    *,
    manifest_path: str,
    start_sec: float,
    end_sec: float,
    budget: int,
    options: FramePoolQueryOptions,
) -> FrameBatch:
    ...
```

输出：

- 文件：`manifest.jsonl`, `shots.json`, `images/...`
- 内存：`FrameBatch`

---

## frame_source

职责：

- 统一不同帧来源
- 屏蔽“均匀抽帧”和“frame pool 抽帧”的差异

建议接口：

```python
def sample_uniform_frames(
    *,
    video_path: str,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    options: UniformFrameOptions,
) -> FrameBatch:
    ...
```

```python
def get_frames_for_segment(
    *,
    video_path: str,
    start_sec: float | None,
    end_sec: float | None,
    duration_sec: float,
    strategy: str,
    frame_pool_manifest: str | None = None,
    options: FrameSourceOptions,
) -> FrameBatch:
    ...
```

输出：

- `FrameBatch`

约束：

- `narration` 不直接知道 `frame_pool_manifest`
- 取帧策略由 orchestration 或 frame_source 负责决定

---

## narration

职责：

- 接收帧和文本上下文
- 组装 prompt
- 调多模态模型生成旁白

建议核心接口：

```python
def narrate_from_frames(
    *,
    frames: FrameBatch,
    context: NarrationContext | None = None,
    prompt_style: str,
    custom_prompt: str = "",
    options: NarrationOptions,
) -> NarrationResult:
    ...
```

兼容层可以保留，但应降级为薄包装：

```python
def narrate_segment_with_duration(...):
    ...
```

兼容层内部只允许：

1. 计算片段时长
2. 调 `frame_source`
3. 调 `narrate_from_frames`

兼容层不应再直接 import `video_frame_pool`。

输出：

- `NarrationResult`

---

## narration_polish

职责：

- 按时长约束压缩或改写旁白
- 满足 CEFR、语速、风格要求

建议接口：

```python
def polish_narration_text(
    text: str,
    duration_sec: float,
    *,
    options: NarrationPolishOptions,
) -> NarrationPolishResult:
    ...
```

输出：

- `NarrationPolishResult`

---

## narration_speech

职责：

- 文本转语音
- 输出音频和对齐元数据

建议接口：

```python
def synthesize_narration_text(
    text: str,
    segment_duration_sec: float,
    *,
    output_path: str,
    metadata_path: str | None,
    options: NarrationSpeechOptions,
) -> NarrationSpeechResult:
    ...
```

输出：

- 文件：音频文件、metadata
- 内存：`NarrationSpeechResult`

约束：

- 不依赖 `narration` 业务模块
- 需要的 `ffprobe`/时长探测功能应来自共享 `media_utils`

---

## narration_video

职责：

- 将旁白音频按时间线混入原视频

建议接口：

```python
def render_narrated_video(
    video_path: str,
    segments: list[NarrationAudioSegment],
    *,
    output_path: str,
    options: NarrationVideoOptions,
) -> NarrationVideoRenderResult:
    ...
```

输出：

- 文件：最终视频
- 内存：`NarrationVideoRenderResult`

约束：

- 不依赖 `narration` 业务模块
- 共享媒体工具应来自 `media_utils`

---

## movie_pipeline

职责：

- 唯一的流程编排层
- 决定哪些模块按什么顺序调用

建议接口：

```python
def run_pipeline(
    *,
    video_path: str,
    srt_path: str,
    pipeline_options: MoviePipelineOptions,
) -> MoviePipelineResult:
    ...
```

它是唯一允许直接串起多个领域模块的地方。

---

## Data Coupling After Refactor

这里描述的是重构后保留的“数据耦合”，不是代码调用关系。

## subtitle_extraction -> subtitle_analysis

耦合数据：

- `.srt`
- `SubtitleCue[]`

说明：

- `subtitle_analysis` 只依赖字幕数据，不依赖 `subtitle_extraction` 的控制流

## subtitle_extraction -> subtitle_context

耦合数据：

- `.srt`
- `SubtitleCue[]`

说明：

- 上下文索引天然来源于字幕内容

## subtitle_extraction -> video_frame_pool

耦合数据：

- `.srt`
- `SubtitleCue[]`

说明：

- 帧池需要知道字幕覆盖区间

## subtitle_analysis -> movie_pipeline

耦合数据：

- `SubtitleAnalysisResult`
- `NarrationCandidate[]`

说明：

- pipeline 只拿到“哪些片段值得生成旁白”

## subtitle_context -> movie_pipeline

耦合数据：

- `RetrievedSubtitleContextChunk[]`

说明：

- pipeline 消费检索结果文本，不依赖索引内部存储格式

## video_frame_pool/frame_source -> movie_pipeline

耦合数据：

- `FrameBatch`

说明：

- 这是本次解耦的核心边界
- `narration` 不再知道 `frame_pool_manifest`

## movie_pipeline -> narration

耦合数据：

- `FrameBatch`
- `NarrationContext`

说明：

- 这是理想的数据耦合
- `narration` 只关心输入帧和文本上下文

## narration -> narration_polish

耦合数据：

- `NarrationResult.text`
- `duration_sec`

## narration_polish -> narration_speech

耦合数据：

- `polished_text`
- `target_duration_sec`

## narration_speech -> narration_video

耦合数据：

- `NarrationAudioSegment[]`

---

## Dependency Direction After Refactor

理想依赖方向如下：

```text
movieteller_config
rerank
media_utils
subtitle_schema
    ↓
subtitle_extraction
subtitle_analysis
subtitle_context
video_frame_pool
frame_source
narration
narration_polish
narration_speech
narration_video
    ↓
movie_pipeline
```

关键要求：

- `subtitle_analysis` 不依赖 `narration`
- `narration` 不依赖 `video_frame_pool`
- `narration_speech` 不依赖 `narration`
- `narration_video` 不依赖 `narration`
- 共享媒体函数抽到 `media_utils`

---

## Configuration Coupling

除了代码依赖，当前还存在隐藏的全局配置耦合。

重构后建议：

1. 入口层只加载一次配置
2. 解析成各模块自己的 options
3. 显式把 options 传入模块

例如：

```python
@dataclass(frozen=True)
class NarrationOptions:
    provider: str
    model: str
    prompt_style: str
    max_edge_pixels: int
```

```python
@dataclass(frozen=True)
class FrameSourceOptions:
    strategy: str
    max_frames_per_segment: int
    frame_pool_manifest: str | None = None
```

这样模块依赖的是自己的显式参数，而不是全局 YAML 状态。

---

## Recommended Refactor Order

建议按下面顺序落地，风险最小。

1. 新增共享 DTO
2. 抽 `media_utils`
3. 在 `narration` 中新增 `narrate_from_frames(...)`
4. 新增 `frame_source`
5. 把 `narration` 中对 `video_frame_pool` 的直接依赖移走
6. 新建 `movie_pipeline`
7. 把 `subtitle_analysis.pipeline` 迁移到 `movie_pipeline`
8. 再收口各模块内部的 `load_settings()` 逻辑

---

## Summary

重构后的核心原则是：

- 业务模块只对自己的输入输出负责
- 模块之间通过稳定 DTO 和文件产物耦合
- 真正的控制流只存在于 `movie_pipeline`

如果按这个方向推进，后续无论接 Node worker、服务端任务队列，还是替换某个模型供应商，都会更稳定。
