# MovieTeller Video Pipeline Refactor Checklist

## Purpose

这份清单把 [video-pipeline-module-boundaries.md](/Users/zhuanz0000/WorkSpace/MovieTeller/docs/video-pipeline-module-boundaries.md) 中的目标边界落成可执行任务。

目标：

- 把 `subtitle_analysis` 收口成纯分析模块
- 把 `narration` 收口成纯旁白生成模块
- 把取帧、字幕上下文、语音、视频合成之间的控制流迁到独立 orchestration 层
- 把“直接模块调用”改成“数据结构连接 + 编排层调用”

---

## Scope

本清单覆盖：

- Python 侧模块边界重构
- CLI 入口迁移
- 共享 DTO / media utils / frame source 的抽离
- 测试与验收

本清单不覆盖：

- Node API / worker / queue 公网部署改造
- 新模型能力接入
- 新的视频理解算法优化

---

## Phase 0: Freeze Current Behavior

### 目标

在重构前固定现有行为，避免边拆边丢能力。

### Tasks

- [ ] 记录当前可用 CLI 入口和典型命令
  - `python -m subtitle_extraction`
  - `python -m subtitle_analysis`
  - `python -m narration`
  - `python -m subtitle_context`
  - `python -m video_frame_pool`
- [ ] 记录当前输出产物格式
  - `.srt`
  - `subtitle_analysis` JSON
  - `subtitle_context` 索引目录
  - `frame_pool` 目录
  - narration JSON / speech audio / rendered video
- [ ] 补一份端到端样例命令到文档，作为回归基线
- [ ] 跑当前核心测试并保存结果

### File Targets

- [docs/video-pipeline-module-boundaries.md](/Users/zhuanz0000/WorkSpace/MovieTeller/docs/video-pipeline-module-boundaries.md)
- 可新增：
  - `docs/video-pipeline-current-behavior.md`

### Acceptance

- [ ] 现有 CLI 能力和产物格式有文档记录
- [ ] 当前测试基线清晰可回归

---

## Phase 1: Extract Shared Media Utilities

### 目标

把 `ffprobe`/时长探测等共享媒体工具从业务模块里抽出来，去掉：

- `narration_speech -> narration.frames`
- `narration_video -> narration.frames`

### Tasks

- [ ] 新建 `python/media_utils/`
- [ ] 抽出以下函数
  - `ffprobe_path_for(...)`
  - `probe_duration_sec(...)`
  - 如需要，再抽 `segment_duration_sec(...)`
- [ ] 修改 `narration` 使用 `media_utils`
- [ ] 修改 `narration_speech` 使用 `media_utils`
- [ ] 修改 `narration_video` 使用 `media_utils`
- [ ] 删除跨业务模块的媒体工具依赖
- [ ] 为 `media_utils` 补测试

### File Targets

- 新增：
  - `python/media_utils/pyproject.toml`
  - `python/media_utils/src/media_utils/__init__.py`
  - `python/media_utils/src/media_utils/probe.py`
  - `python/media_utils/tests/test_probe.py`
- 修改：
  - [python/narration/src/narration/frames.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/frames.py)
  - [python/narration_speech/src/narration_speech/speech.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration_speech/src/narration_speech/speech.py)
  - [python/narration_video/src/narration_video/render.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration_video/src/narration_video/render.py)
  - 各自 `pyproject.toml`

### Acceptance

- [ ] `narration_speech` 不再 import `narration.frames`
- [ ] `narration_video` 不再 import `narration.frames`
- [ ] 相关测试通过

---

## Phase 2: Stabilize Shared DTOs

### 目标

把跨模块传输的数据结构显式化，避免临时 dict 和隐式字段扩散。

### Tasks

- [ ] 新建共享 schema 包
  - 建议 `python/pipeline_types/` 或 `python/media_types/`
- [ ] 迁移或复制以下 DTO
  - `SubtitleCue`
  - `NarrationCandidate`
  - `FrameBatch`
  - `NarrationContext`
  - `NarrationResult`
  - `NarrationAudioSegment`
- [ ] 让各模块优先依赖共享 DTO，而不是跨模块内部类型
- [ ] 为 DTO 兼容层补测试

### File Targets

- 新增：
  - `python/pipeline_types/pyproject.toml`
  - `python/pipeline_types/src/pipeline_types/__init__.py`
  - `python/pipeline_types/src/pipeline_types/subtitle.py`
  - `python/pipeline_types/src/pipeline_types/narration.py`
  - `python/pipeline_types/tests/test_types.py`
- 修改：
  - [python/subtitle_analysis/src/subtitle_analysis/types.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/src/subtitle_analysis/types.py)
  - [python/subtitle_extraction/src/subtitle_extraction/types.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_extraction/src/subtitle_extraction/types.py)
  - [python/narration_video/src/narration_video/types.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration_video/src/narration_video/types.py)
  - [python/video_frame_pool/src/video_frame_pool/types.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/video_frame_pool/src/video_frame_pool/types.py)

### Acceptance

- [ ] `FrameBatch` 成为取帧到旁白之间的标准输入
- [ ] `NarrationContext` 成为字幕上下文到旁白之间的标准输入
- [ ] 新 DTO 在至少两个模块中实际使用

---

## Phase 3: Introduce frame_source Layer

### 目标

把“均匀抽帧”和“frame pool 取帧”统一到独立 `frame_source` 层，让 `narration` 不再知道取帧策略。

### Tasks

- [ ] 新建 `python/frame_source/`
- [ ] 封装统一抽帧接口
  - `sample_uniform_frames(...)`
  - `get_frames_for_segment(...)`
- [ ] 增加 `frame_pool` 适配入口
  - `query_frame_pool_as_frame_batch(...)`
- [ ] 定义标准返回 `FrameBatch`
- [ ] 为策略切换和 fallback 补测试

### File Targets

- 新增：
  - `python/frame_source/pyproject.toml`
  - `python/frame_source/src/frame_source/__init__.py`
  - `python/frame_source/src/frame_source/uniform.py`
  - `python/frame_source/src/frame_source/router.py`
  - `python/frame_source/tests/test_router.py`
- 修改：
  - [python/video_frame_pool/src/video_frame_pool/query.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/video_frame_pool/src/video_frame_pool/query.py)
  - [python/video_frame_pool/src/video_frame_pool/__init__.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/video_frame_pool/src/video_frame_pool/__init__.py)
  - [python/narration/src/narration/frames.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/frames.py)

### Acceptance

- [ ] `frame_source` 可返回统一 `FrameBatch`
- [ ] `frame_pool` 查询结果可直接转成 `FrameBatch`
- [ ] 均匀抽帧和 frame pool 都能通过同一入口调用

---

## Phase 4: Shrink narration To Pure Generation

### 目标

把 `narration` 收口成“消费帧 + 消费文本上下文 -> 生成旁白”。

### Tasks

- [ ] 在 `narration` 中新增核心接口
  - `narrate_from_frames(...)`
- [ ] 明确输入
  - `FrameBatch`
  - `NarrationContext`
- [ ] 把 prompt 组装逻辑统一基于显式 context
- [ ] 保留 `narrate_segment_with_duration(...)` 作为兼容层
- [ ] 兼容层内部改为调用 `frame_source`
- [ ] 删除 `narration` 中对 `video_frame_pool` 的直接 import
- [ ] 删除 `narration` 中对 `subtitle_context` 的直接检索逻辑

### File Targets

- 修改：
  - [python/narration/src/narration/narrate.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/narrate.py)
  - [python/narration/src/narration/prompts.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/prompts.py)
  - [python/narration/src/narration/__init__.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/__init__.py)
  - [python/narration/tests/test_narrate_mock.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/tests/test_narrate_mock.py)
  - [python/narration/tests/test_prompts.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/tests/test_prompts.py)

### Acceptance

- [ ] `narration` 不再 import `video_frame_pool`
- [ ] `narration` 不再直接 import `subtitle_context`
- [ ] `narrate_from_frames(...)` 成为主推荐接口
- [ ] 旧 CLI 仍能工作或有明确迁移方案

---

## Phase 5: Make subtitle_analysis Pure Again

### 目标

移除 `subtitle_analysis` 中的总流程编排能力，只保留字幕分析。

### Tasks

- [ ] 把 `subtitle_analysis.pipeline` 中的总流程迁走
- [ ] 从 `subtitle_analysis.__init__` 中移除
  - `analyze_and_narrate`
  - `narrate_analysis_candidates`
- [ ] 保留：
  - `analyze_subtitle_cues`
  - `analyze_subtitle_file`
  - `result_to_dict`
  - `result_to_json`
- [ ] 精简 CLI，只保留分析命令
- [ ] 更新 README，明确不再负责旁白总流程

### File Targets

- 修改：
  - [python/subtitle_analysis/src/subtitle_analysis/__init__.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/src/subtitle_analysis/__init__.py)
  - [python/subtitle_analysis/src/subtitle_analysis/__main__.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/src/subtitle_analysis/__main__.py)
  - [python/subtitle_analysis/README.md](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/README.md)
  - [python/subtitle_analysis/pyproject.toml](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/pyproject.toml)
- 删除或迁移：
  - [python/subtitle_analysis/src/subtitle_analysis/pipeline.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis/src/subtitle_analysis/pipeline.py)

### Acceptance

- [x] `subtitle_analysis` 只暴露分析接口
- [x] `subtitle_analysis` 不再直接调用 `narration`
- [x] 包依赖声明与实际实现一致

---

## Phase 6: Create movie_pipeline Orchestration Module

### 目标

把原来散落在 `subtitle_analysis.pipeline` 和 `narration` 内部的控制流迁移到单独 orchestration 层。

### Tasks

- [ ] 新建 `python/movie_pipeline/`
- [ ] 提供统一入口
  - `run_pipeline_ctx(..., ctx=RunContext(...))`
- [ ] 在这里串起：
  - `subtitle_analysis`
  - `subtitle_context`
  - `frame_source`
  - `narration`
  - `narration_polish`
  - `narration_speech`
  - `narration_video`
- [ ] 把“是否检索字幕上下文”“是否走 frame_pool”“是否润色”“是否合成视频”等决策放到这里
- [ ] 补端到端 mock 测试
- [ ] 提供新的总流程 CLI

### File Targets

- 新增：
  - `python/movie_pipeline/pyproject.toml`
  - `python/movie_pipeline/src/movie_pipeline/__init__.py`
  - `python/movie_pipeline/src/movie_pipeline/pipeline.py`
  - `python/movie_pipeline/src/movie_pipeline/cli.py`
  - `python/movie_pipeline/src/movie_pipeline/__main__.py`
  - `python/movie_pipeline/tests/test_pipeline_mock.py`

### Acceptance

- [x] 总流程能力只存在于 `movie_pipeline`
- [x] 旧的 `subtitle_analysis --narrate` 有迁移路径
- [x] 编排顺序可以只通过 mock 测试验证，不依赖真实外部 API

---

## Phase 7: Reduce Global Config Coupling

### 目标

把模块内部零散的 `load_settings()` 收口成“入口加载一次，再显式传 options”。

### Tasks

- [ ] 为各模块定义专属 options/dataclass
  - `NarrationOptions`
  - `FrameSourceOptions`
  - `SubtitleContextBuildOptions`
  - `SubtitleContextRetrieveOptions`
  - `NarrationPolishOptions`
  - `NarrationSpeechOptions`
  - `NarrationVideoOptions`
- [ ] orchestration 层负责从 `movieteller_config` 解析这些 options
- [ ] 各模块核心能力函数优先接收显式 options
- [ ] `load_settings()` 仅保留在 CLI / 兼容入口 / orchestrator 中

### File Targets

- 修改：
  - [python/movieteller_config/src/movieteller_config/schema.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/movieteller_config/src/movieteller_config/schema.py)
  - [python/narration/src/narration/narrate.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration/src/narration/narrate.py)
  - [python/narration_polish/src/narration_polish/polish.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration_polish/src/narration_polish/polish.py)
  - [python/narration_speech/src/narration_speech/speech.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration_speech/src/narration_speech/speech.py)
  - [python/subtitle_context/src/subtitle_context/index.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_context/src/subtitle_context/index.py)
  - [python/video_frame_pool/src/video_frame_pool/build.py](/Users/zhuanz0000/WorkSpace/MovieTeller/python/video_frame_pool/src/video_frame_pool/build.py)

### Acceptance

- [x] 核心函数大多不再隐式读全局配置
- [x] CLI 和 orchestrator 是主要配置装配入口

---

## Phase 8: CLI Migration And Compatibility

### 目标

把旧 CLI 的职责重新分配，同时保证迁移过程可用。

### Tasks

- [ ] 保留纯分析 CLI
  - `python -m subtitle_analysis`
- [ ] 保留纯旁白 CLI
  - `python -m narration`
- [ ] 新增总流程 CLI
  - `python -m movie_pipeline`
- [ ] 视情况保留旧参数兼容层
- [ ] 在 README 中增加迁移示例

### Acceptance

- [x] 用户能明确知道哪个 CLI 属于哪个职责
- [x] 不再通过 `subtitle_analysis` 承担视频全流程

---

## Phase 9: Testing And Regression

### 目标

保证重构后边界更清晰，同时已有核心能力不回退。

### Tasks

- [ ] 为新增共享层补测试
  - `media_utils`
  - `pipeline_types`
  - `frame_source`
  - `movie_pipeline`
- [ ] 更新现有模块测试
- [ ] 增加模块边界测试
  - `subtitle_analysis` 不 import `narration`
  - `narration` 不 import `video_frame_pool`
  - `narration_speech` 不 import `narration`
  - `narration_video` 不 import `narration`
- [ ] 跑完整核心测试集

### Acceptance

- [ ] 重构前后的关键用例都能跑通
- [ ] 新边界有测试保护

---

## Suggested Execution Order

建议按下面顺序推进，风险最小：

1. `media_utils`
2. 共享 DTO
3. `frame_source`
4. `narration` 纯化
5. `subtitle_analysis` 纯化
6. `movie_pipeline`
7. 配置耦合收口
8. CLI 迁移
9. 回归测试与文档更新

---

## Definition Of Done

当以下条件都满足时，认为重构完成：

- [x] `subtitle_analysis` 只负责字幕分析
- [x] `narration` 只负责旁白生成
- [x] `movie_pipeline` 成为唯一总流程编排层
- [x] `video_frame_pool` 与 `narration` 之间只通过 `FrameBatch` 耦合
- [x] `subtitle_context` 与 `narration` 之间只通过 `NarrationContext` 中的文本字段耦合
- [x] `narration_speech` 和 `narration_video` 不再依赖 `narration` 业务模块
- [x] 核心配置通过显式 options 传递
- [x] 相关测试通过
- [x] README / docs 已同步更新

---

## Notes

- 当前规范入口已经切到 `python -m movie_pipeline` 和 `run_pipeline_ctx(..., ctx=RunContext(...))`。
- `analyze_and_narrate(...)` 仍保留，但仅作为兼容包装层。
- 优先保证边界清晰，再考虑进一步优化内部实现。
