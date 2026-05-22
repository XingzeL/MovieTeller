# MovieTeller Pipeline Parallelization Plan

## 目标

当前流水线的主要耗时集中在按片段执行的模型调用和语音合成上。并行化的目标不是把全项目改成 async，而是在保持阶段边界清晰的前提下，把天然独立的 segment 任务做有限并发。

核心目标：

- 长视频处理时间随 segment 数量下降。
- 输出 payload 顺序保持稳定，仍按时间线排列。
- 功能模块不直接管理线程池、不直接读取并发配置。
- 并发失败可定位到具体 stage 和 segment。
- 后续可以自然接入 API job queue 和前端进度。

## 总体方案

推荐形态是同步 workflow 编排 + 阶段内有限并发 + API 层异步 job。

```text
Frontend / API
  -> WorkflowRequest
  -> Settings
  -> PolicyContext
  -> ResolvedRunContext
  -> Job Queue
  -> Workflow Worker
  -> run_full_workflow(ctx)
```

workflow 内部保持阶段 DAG：

```text
Subtitle Extraction
  -> Frame Pool Build
  -> Subtitle Context Build
  -> Candidate Detection
  -> Parallel Vision Narration
  -> Parallel Polish
  -> Parallel TTS
  -> Subtitle Merge
  -> Video Render
  -> Derived Artifact Export
```

真正并发的部分：

- `Vision Narration per segment`
- `Polish per segment`
- `TTS per segment`
- `Study cards asset preparation`

保持顺序执行的部分：

- `Subtitle Extraction`
- `Frame Pool Build`
- `Subtitle Context Build`
- `Candidate Detection`
- `Subtitle Merge`
- `Final Video Render`
- `Payload checkpoint write`
- `Artifact index update`

## 架构图

```text
Workflow Worker
  |
  v
+---------------------------------------------------------------+
| run_full_workflow(resolved_context)                           |
|                                                               |
|  [1] stage_subtitle_extraction                                |
|       |                                                       |
|       v                                                       |
|  [2] stage_frame_pool                                         |
|       |                                                       |
|       v                                                       |
|  [3] stage_subtitle_context                                   |
|       |                                                       |
|       v                                                       |
|  [4] stage_narration_pipeline                                 |
|       |                                                       |
|       +-- StageExecutor.map_ordered(stage="narration")        |
|       |      +-- segment 001 -> frames -> VLM API             |
|       |      +-- segment 002 -> frames -> VLM API             |
|       |      +-- segment 003 -> frames -> VLM API             |
|       |                                                       |
|       +-- StageExecutor.map_ordered(stage="polish")           |
|       |      +-- segment 001 -> LLM polish                    |
|       |      +-- segment 002 -> LLM polish                    |
|       |      +-- segment 003 -> LLM polish                    |
|       |                                                       |
|       +-- StageExecutor.map_ordered(stage="tts")              |
|              +-- segment 001 -> TTS -> segment_0001.mp3       |
|              +-- segment 002 -> TTS -> segment_0002.mp3       |
|              +-- segment 003 -> TTS -> segment_0003.mp3       |
|                                                               |
|  [5] stage_video_package                                      |
|       |                                                       |
|       v                                                       |
|  [6] export_workflow_artifacts                                |
|                                                               |
+---------------------------------------------------------------+
```

## 并发原则

### 阶段内并发

每个阶段独立并发，阶段之间同步等待。

推荐：

```text
先并发完成所有 narration
再并发完成所有 polish
再并发完成所有 TTS
```

不推荐：

```text
segment 001: narration -> polish -> TTS
segment 002: narration -> polish -> TTS
segment 003: narration -> polish -> TTS
```

原因是阶段内并发更容易保序、落盘、恢复和定位失败。

### 有限并发

所有模型调用必须限制并发，不允许无限 `gather` 或无限线程池。

建议初始配置：

```yaml
workflow_concurrency:
  narration: 2
  polish: 4
  tts: 3
  artifact_assets: 4
```

后续可以由用户等级、模型供应商、key 池状态覆盖这些值。

### 保序回填

并发执行可以乱序完成，但返回结果必须按输入顺序排列。

payload 中的 `narratedSegments` 必须始终按时间线输出。

### 功能模块不管理并发

并发策略只属于执行器层。功能模块只负责处理一个输入。

```text
pipeline stage: 决定处理哪些 segment
StageExecutor: 决定如何并发、如何保序、如何重试
narrator/polisher/tts: 处理单个 segment
workflow: 决定阶段顺序
```

## StageExecutor 设计

新增模块建议：

```text
python/movie_pipeline/src/movie_pipeline/stage_executor.py
```

核心接口：

```python
class StageExecutor:
    def map_ordered(
        self,
        items,
        fn,
        *,
        concurrency: int,
        stage_name: str,
        progress=None,
    ):
        ...
```

职责：

- 限制并发。
- 保序返回。
- 捕获异常并标注 stage/index。
- 支持基础重试。
- 支持进度回调。
- 统一日志字段。

第一版可以使用 `ThreadPoolExecutor`，不要急着全链路 `asyncio`。

原因：

- 当前大量 SDK 和 ffmpeg 调用是阻塞式。
- OpenAI-compatible、DashScope、文件 IO、音视频处理都可以先用线程池包住。
- workflow 入口保持同步，减少调用链重构成本。

## 配置设计

配置只表达策略，不散落到功能模块。

建议新增：

```yaml
workflow_concurrency:
  narration: 2
  polish: 4
  tts: 3
  artifact_assets: 4
```

解析后进入 `Settings`，再由 resolver 合成运行时配置。

推荐传递链路：

```text
local.yaml
  -> Settings
  -> PolicyContext override
  -> ResolvedExecutionConfig
  -> ResolvedRunContext
  -> StageExecutor
```

不要让 `narration`、`narration_polish`、`narration_speech` 直接读取 settings。

## 阶段改造方案

### 1. Vision Narration 并发

目标位置：

```text
movie_pipeline.pipeline.narrate_analysis_candidates
```

当前形态通常是按 candidate 循环调用 narrator。目标是把单个 candidate 的处理提成纯函数，然后交给 executor。

目标结构：

```text
candidates
  -> map_ordered(narrate_one_candidate, concurrency=narration)
  -> narrated segments
```

注意点：

- `timings_out` 必须是每个任务独立对象。
- 日志必须带 `segment_index`、`start_sec`、`end_sec`。
- frame source 如果会写临时文件，必须确认文件名不会冲突。
- 模型 client 不明确线程安全时，每个 worker 内部创建 client。

### 2. Polish 并发

目标位置：

```text
movie_pipeline.pipeline.narrate_analysis_candidates
```

或拆出独立 stage：

```text
polish_narrated_segments
```

推荐先完成所有 narration，再并发 polish。

目标结构：

```text
narrated segments
  -> map_ordered(polish_one_segment, concurrency=polish)
  -> polished segments
```

注意点：

- 输入 segment 应不可变，输出新 segment。
- `sceneTitleZh` 等字段按 segment 回填。
- polish 失败时明确是 fallback 原文还是中止。

### 3. TTS 并发

目标位置：

```text
movie_pipeline.pipeline.narrate_analysis_candidates
```

或拆出独立 stage：

```text
synthesize_speech_for_segments
```

目标结构：

```text
polished segments
  -> map_ordered(synthesize_one_segment, concurrency=tts)
  -> speech segments
```

注意点：

- 音频文件名必须由 segment index 决定，不能由完成顺序决定。
- metadata 文件名必须同样稳定。
- 同一目录并发写必须无冲突。
- TTS 失败后 `stage_video_package` 必须能判断是否允许继续。

推荐命名：

```text
segment_0001.mp3
segment_0001.metadata.json
segment_0002.mp3
segment_0002.metadata.json
```

### 4. Artifact Export 并发

当前学习卡导出已经从主流程抽到：

```text
movie_pipeline.workflow_exports
movie_pipeline.study_cards_export
movie_pipeline.study_cards_html
```

后续如果 HTML 中外部资源很多，可以只并发资源准备，不并发最终 HTML 写入。

目标结构：

```text
StudyCardsDocument
  -> map_ordered(prepare_frame_asset, concurrency=artifact_assets)
  -> render one HTML file
```

## 错误模型

并发之后，错误应该分层。

### Fatal stage failure

直接中止 workflow。

适用阶段：

- subtitle extraction
- frame pool build
- subtitle context build
- final video render

### Segment failure

记录到具体 segment。

适用阶段：

- narration
- polish
- tts

建议字段：

```json
{
  "stageErrors": [
    {
      "stage": "tts",
      "message": "...",
      "retryable": true
    }
  ]
}
```

第一版可以只记录：

```text
stage
message
retryable
```

### Optional artifact failure

不影响主流程，只写入 `workflowArtifacts`。

例子：

```json
{
  "workflowArtifacts": {
    "studyCardsHtmlPath": null,
    "studyCardsHtmlError": "..."
  }
}
```

## Checkpoint / Resume

并发化后建议强化阶段落盘。

推荐 checkpoint：

```text
pipeline.text.json
pipeline.polished.json
pipeline.speech.json
pipeline.render.json
```

规则：

- 阶段内并发期间不写共享 JSON。
- 阶段完成后统一写 checkpoint。
- resume 时校验 JSON 和 artifact 是否同时存在。
- 缺音频文件时，不能只相信 speech JSON。

这和现有“从 text JSON 继续 speech/video”的方向一致。

## API 层异步化

API 层异步化应该晚于内部并发。

推荐接口：

```text
POST /workflows
GET /workflows/{job_id}
GET /workflows/{job_id}/events
POST /workflows/{job_id}/cancel
```

执行模型：

```text
API process
  -> validate request
  -> create job
  -> enqueue job
  -> return job_id

Worker process
  -> load Settings
  -> resolve PolicyContext
  -> build ResolvedRunContext
  -> run workflow with StageExecutor
  -> update job progress
```

前端不应该同步等待完整视频生成。

## 实施计划

### Phase 1: Executor 基础设施

目标：建立统一并发入口，不改业务结果。

任务：

- 新增 `stage_executor.py`。
- 实现 `map_ordered`。
- 支持 `concurrency=1` 的同步等价路径。
- 支持异常包装和 stage/index 信息。
- 增加 executor 单元测试。

验收：

- 输入乱序完成，输出仍保序。
- `concurrency=1` 行为和普通循环一致。
- 异常能定位到 stage 和 index。

难度：低-中。

### Phase 2: 配置并发参数

目标：并发参数进入统一配置和 resolver。

任务：

- 在 config example 中新增 `workflow_concurrency`。
- 在 `Settings` 中增加解析结构。
- 在 `ResolvedExecutionConfig` 或专用 runtime config 中承载并发策略。
- 不让功能模块直接读 settings。

验收：

- 默认配置无需用户改动即可运行。
- 测试可覆盖默认值和 override。

难度：低。

### Phase 3: Narration 并发

目标：最大耗时阶段并发化。

任务：

- 拆出 `narrate_one_candidate`。
- 使用 `StageExecutor.map_ordered`。
- 每个任务独立 timings。
- 保持 `narratedSegments` 顺序不变。
- 增加并发保序测试。

验收：

- mock narrator 加 sleep 后，输出仍按时间排序。
- payload shape 不变。
- 串行和并发结果一致。

难度：中。

### Phase 4: Polish 并发

目标：文本润色阶段并发化。

任务：

- 拆出 `polish_one_segment`。
- 使用独立 concurrency。
- polish 失败策略明确化。
- 更新测试覆盖 `sceneTitleZh` 回填。

验收：

- polish 结果按 segment 回填。
- polish disabled 时不创建 executor 任务。

难度：中。

### Phase 5: TTS 并发

目标：语音生成阶段并发化。

任务：

- 拆出 `synthesize_one_segment`。
- 文件名改为 index-stable。
- 并发写同目录无冲突。
- TTS 失败写 segment error。

验收：

- 多 segment 并发生成音频路径稳定。
- 输出 JSON 顺序稳定。
- 缺音频时 render 阶段能明确报错。

难度：中-高。

### Phase 6: Segment Error Model

目标：并发失败可恢复、可展示。

任务：

- 增加 `stageErrors` payload 字段。
- 定义 `stage/message/retryable`。
- executor 失败结果转换到 segment error。
- 明确哪些 stage 允许 partial failure。

验收：

- 单 segment TTS 失败不会丢失其他 segment 结果。
- fatal stage 仍直接失败。

难度：中。

### Phase 7: Checkpoint / Resume

目标：长视频失败后避免重跑昂贵阶段。

任务：

- 标准化 text/polished/speech/render checkpoint。
- 阶段完成后统一写 JSON。
- resume 时校验 JSON + artifact 文件。
- 手动测试脚本优先使用已有 checkpoint。

验收：

- text JSON 存在时不重跑视觉理解。
- speech JSON 存在且音频完整时不重跑 TTS。
- artifact 缺失时能准确提示。

难度：中-高。

### Phase 8: API Job Queue

目标：前端请求异步化。

任务：

- 新增 job model。
- 新增 queue 和 worker。
- API 返回 `job_id`。
- worker 更新进度和 artifact。
- 增加取消任务能力。

验收：

- 前端提交后立即返回。
- 可查询阶段进度。
- worker 崩溃后 job 状态可恢复或明确失败。

难度：高。

### Phase 9: Progress Events

目标：前端实时展示进度。

任务：

- 定义 progress event。
- executor 每完成一个 item 上报。
- 支持 SSE 或轮询。
- 日志、job status、前端事件使用同一进度模型。

验收：

- 前端可看到 `narrating 8/21`。
- 失败事件包含 stage 和 segment index。

难度：中-高。

## 风险清单

高风险：

- SDK client 线程安全不明确。
- TTS 并发写文件冲突。
- provider 限流导致失败率上升。
- payload 顺序被完成顺序污染。
- 并发日志无法对应 segment。

中风险：

- frame source 临时文件冲突。
- checkpoint 与 artifact 不一致。
- retry 导致重复计费。
- progress 统计和真实完成状态不一致。

低风险：

- HTML asset 并发准备。
- polish 文本阶段并发。

## 不建议做的事

- 不要把 `run_full_workflow` 整体改成 `async def`。
- 不要让每个 provider adapter 自己控制并发。
- 不要无限 `asyncio.gather`。
- 不要并发写同一个 payload JSON。
- 不要把 segment 一路异步流水到底，第一版先阶段内并发。
- 不要让功能模块直接读 `Settings.workflow_concurrency`。

## 推荐最小落地路线

第一轮：

```text
StageExecutor
  -> workflow_concurrency defaults
  -> narration 并发
  -> 保序测试
```

第二轮：

```text
polish 并发
  -> TTS 并发
  -> segment error model
```

第三轮：

```text
checkpoint/resume
  -> API job queue
  -> progress events
```

## 一句话结论

MovieTeller 最适合的并行化方案是：主 workflow 保持同步 DAG 编排，阶段内部通过统一 `StageExecutor` 做有限并发和保序回填，API 层通过 job queue 对前端异步化。
