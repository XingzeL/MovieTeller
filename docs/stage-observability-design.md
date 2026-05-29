# Stage Observability Design

> **落地状态（2026-05）**：已按 [observability-95-landing.md](./observability-95-landing.md) 完成 B1–B4。宏阶段**仅** `workflow.stage.*`；`progress` / `overall_progress` 只读这些事件推进宏阶段；legacy 宏事件（`subtitle_extraction.start` 等）已从代码与 `events.py` 删除。

目标：把产品化路线图「阶段一：日志与可观测性」中固定 stage 的生命周期日志覆盖率提升到 90% 以上，并降低实现「所有固定 stage 都有 start/done/failed/skipped」的不确定性。

## 背景

当前主链路已经具备文件态 Job、JSONL 日志、进度读取、前端日志 UI、gateway timeout/retry 与取消信号。现有 stage 日志主要分散在：

- `python/movie_pipeline/src/movie_pipeline/full_workflow.py`
- `python/movie_pipeline/src/movie_pipeline/workflow_stages.py`
- `python/movie_pipeline/src/movie_pipeline/pipeline.py`
- `python/movieteller_logging/src/movieteller_logging/events.py`

目前已经有部分 `start/done/failed`：`subtitle_extraction`、`frame_pool`、`subtitle_context`、`video_package`、`workflow_export`、segment 级 narration / polish / study / tts。但路线图中的固定 stage 更细：

```text
ingest
subtitle_extraction
subtitle_analysis
frame_pool
subtitle_context
narration
polish
study_enrichment
tts
subtitle_merge
render
export
```

历史缺口（已收口）：`subtitle_analysis` / `polish` / `study_enrichment` 等在 `run_pipeline_ctx` 内用 `StageLogger`；外层 `render` / `export` 与 `FIXED_WORKFLOW_STAGES` 对齐。

## 设计原则

1. **单一宏阶段事件源**：固定 stage 生命周期只发 `workflow.stage.*`，不保留 parallel legacy 宏事件。
2. **stage 名称稳定**：JSONL `stage` 使用 `movieteller_logging.events.FIXED_WORKFLOW_STAGES` 中的 id（含 `render`、`export`）。
3. **进度只读标准事件**：`progress_from_jsonl` / CLI `overall_progress` 的宏 `current_stage` 与 `x_*` artifact 仅来自 `workflow.stage.*`。
4. **skipped 有明确原因**：凡是 `status=skipped` 的事件必须带 `skip_reason`，例如 `disabled_by_request`、`artifact_reused`、`checkpoint_valid`、`not_requested`。
5. **不伪造不可观测阶段**：如果当前实现无法把某个逻辑拆成独立阶段，不在 runtime 中硬造耗时；先在设计中标注落点，再在代码中增加 wrapper。
6. **测试驱动补齐**：新增 mock workflow 日志契约测试，先保证每个固定 stage 至少出现一个标准终态事件，再逐步断言字段完整性。

## 标准事件契约

在 `movieteller_logging/events.py` 增加：

```python
WORKFLOW_STAGE_START = "workflow.stage.start"
WORKFLOW_STAGE_DONE = "workflow.stage.done"
WORKFLOW_STAGE_FAILED = "workflow.stage.failed"
WORKFLOW_STAGE_SKIPPED = "workflow.stage.skipped"
```

### `workflow.stage.start`

必备字段：

```json
{
  "event": "workflow.stage.start",
  "stage": "narration",
  "status": "start",
  "job_id": "...",
  "x_output_root": "..."
}
```

推荐字段：

- `stage_index`
- `stage_total`
- `input_path`
- `input_count`
- `force_rebuild`
- `enabled`

### `workflow.stage.done`

必备字段：

```json
{
  "event": "workflow.stage.done",
  "stage": "narration",
  "status": "ok",
  "duration_ms": 1234
}
```

推荐字段：

- `output_path`
- `output_count`
- `segment_count`
- `artifact_reused`

### `workflow.stage.skipped`

必备字段：

```json
{
  "event": "workflow.stage.skipped",
  "stage": "subtitle_context",
  "status": "skipped",
  "duration_ms": 12,
  "skip_reason": "disabled_by_request"
}
```

允许的 `skip_reason` 第一版枚举：

- `disabled_by_request`
- `artifact_reused`
- `checkpoint_valid`
- `not_requested`
- `no_segments`
- `no_output_requested`

### `workflow.stage.failed`

必备字段：

```json
{
  "event": "workflow.stage.failed",
  "stage": "tts",
  "status": "error",
  "duration_ms": 1234,
  "error_code": "provider_timeout",
  "error_message": "...",
  "fatal": true,
  "retryable": true
}
```

## Stage 覆盖矩阵

| 固定 stage | 当前落点 | 当前状态 | 90%+ 实现策略 | skipped 来源 |
|---|---|---:|---|---|
| `ingest` | Node `createJobFromUpload` + Python `run_workflow_job` | 弱 | Python runner 启动后立刻写标准 `ingest.start/done`，记录 `input_video_path`、`request_json`；Node 上传校验失败保持 HTTP 错误，不进入 Job 日志 | 通常不 skip |
| `subtitle_extraction` | `stage_subtitle_extraction` | 已落地 | 仅 `workflow.stage.*`；`SubtitleExtractionPolicy` 决定 done/skipped | `artifact_reused` 或 `disabled_by_request` |
| `subtitle_analysis` | `run_pipeline_ctx` 内部 | 中 | 在 `run_pipeline_ctx` 读取/分析 SRT 的边界加 wrapper；成功后记录 subtitle span / candidate 数 | 若未来有 analysis artifact 可 `artifact_reused`；第一版通常不 skip |
| `frame_pool` | `stage_frame_pool` | 已落地 | 仅 `workflow.stage.*` | `artifact_reused` 或 `disabled_by_request` |
| `subtitle_context` | `stage_subtitle_context` | 已落地 | 仅 `workflow.stage.*` | `disabled_by_request`、`artifact_reused` |
| `narration` | `run_pipeline_ctx` / segment events | 中 | 在 segment group narration 外围增加 stage wrapper；汇总 segment count、group count、失败 segment | 无候选时 `no_segments`；未来 narration artifact 可 `artifact_reused` |
| `polish` | `PipelineSegmentExecutor` segment polish | 中 | 将 `enable_polish=False` 显式写 stage skipped；启用时 wrapper 汇总 polish segment 数 | `disabled_by_request`、`no_segments` |
| `study_enrichment` | `PipelineSegmentExecutor` segment study | 中 | 将 non-fatal failed 仍写 stage done with warnings，同时 segment failed 保留 warning；禁用/无词卡写 skipped | `disabled_by_request`、`no_segments`、`not_requested` |
| `tts` | `PipelineSegmentExecutor` segment tts | 中偏好 | 现有 segment `tts.start/done/skipped` 可汇总为 stage wrapper；`enable_speech=False` 写 skipped | `disabled_by_request`、`artifact_reused`、`no_segments` |
| `subtitle_merge` | 当前不明显，可能在 speech/video payload 内 | 弱 | 第一版在生成最终字幕/语音 payload 的函数边界加 wrapper；若无独立产物则记录 `no_output_requested` skipped | `no_output_requested` |
| `render` | `stage_video_package` | 已落地 | `StageLogger("render")`；无 `video_package.*` 事件 | `disabled_by_request` |
| `export` | `full_workflow` + `export_workflow_artifacts` | 已落地 | `StageLogger("export")` 包住导出与 product manifest | 通常不 skip |

## 推荐实现分层

### 1. StageLogger helper

新增轻量 helper，建议位置：`movie_pipeline/stage_observability.py`。

职责：

- 统一 `start/done/skipped/failed` 写法。
- 自动计算 `duration_ms`。
- 在失败时调用 `classify_error()`。

建议接口：

```python
class StageLogger:
    def __init__(self, stage: str, **fields): ...
    def start(self): ...
    def done(self, **fields): ...
    def skipped(self, skip_reason: str, **fields): ...
    def failed(self, exc: BaseException, *, fatal: bool = True, **fields): ...
```

也可以提供 context manager：

```python
with observe_stage("frame_pool", input_path=paths.srt_path) as stage:
    if should_skip:
        stage.skipped("artifact_reused")
        return
    ...
    stage.done(output_path=paths.frame_pool_manifest)
```

### 2. 先包外层 stage，再细化 pipeline 内部

第一批低风险落点：

- `stage_subtitle_extraction`
- `stage_frame_pool`
- `stage_subtitle_context`
- `stage_video_package`（标准 stage 写 `render`）
- `full_workflow.py` 中 `export_workflow_artifacts` 前后
- `job_runner/core.py` 或 `full_workflow.py` 中 ingest

第二批中风险落点：

- `run_pipeline_ctx` 内的 `subtitle_analysis`
- `PipelineSegmentExecutor` 外围的 `narration`、`polish`、`study_enrichment`、`tts` 汇总事件

第三批需要确认语义的落点：

- `subtitle_merge`，需先确认最终字幕文件生成位置和是否有独立 artifact。

## 实施计划

### Milestone A：契约与低风险 stage（置信度高）

1. 在 `events.py` 增加标准事件。
2. 新增 `StageLogger`。
3. 为 `subtitle_extraction`、`frame_pool`、`subtitle_context`、`render`、`export`、`ingest` 写标准事件。
4. 保留现有旧事件。
5. 添加测试：这些 stage 的 `workflow.stage.*` 必定出现。

预期收益：固定 stage 覆盖从 75% 提升到约 82%。

### Milestone B：pipeline 内部阶段汇总（置信度中高）

1. 在 `run_pipeline_ctx` 中围绕 subtitle analysis 写标准事件。
2. 在 segment executor 上层或批处理入口写 narration/polish/study_enrichment/tts stage 汇总事件。
3. 将 `enable_polish=False`、`enable_speech=False` 明确写为 skipped。
4. study enrichment 保持 non-fatal，但 stage 汇总需要输出 `warning_count`。

预期收益：覆盖提升到约 88%～90%。

### Milestone C：subtitle_merge 与严格契约测试（需小范围探索）

1. 找到最终字幕合并/语音视频 payload 产物边界。
2. 若存在独立文件，写 `subtitle_merge.start/done/failed/skipped`。
3. 若当前无独立产物，第一版写 `subtitle_merge.skipped`，`skip_reason=no_output_requested` 或 `not_implemented_as_separate_stage`，并在路线图记录待拆分。
4. 增加 mock workflow 契约测试，断言 12 个固定 stage 都有 start + 终态，或有文档允许的 skip。

预期收益：覆盖稳定在 90%+。

## 测试策略

### 单元测试

- `python/movieteller_logging/tests/test_events.py`：标准事件常量存在且命名符合 `workflow.stage.*`。
- `python/movie_pipeline/tests/test_stage_observability.py`：`StageLogger` 正确写 start/done/skipped/failed，失败事件包含 `error_code`。

### Mock workflow 契约测试

建议新增：`python/movie_pipeline/tests/test_workflow_stage_observability_contract.py`。

用 mock narrator / polisher / synthesizer / renderer 跑最小 workflow，读取 `logs/workflow.jsonl`，断言：

- 每个固定 stage 至少有一个标准 lifecycle 事件。
- 每个 stage 有 `start` 后必须有 `done` / `skipped` / `failed` 之一。
- `failed` 必须包含 `error_code`、`error_message`、`fatal`。
- `skipped` 必须包含 `skip_reason`。
- `duration_ms` 在终态事件中存在。

### Resume / skip 测试

对已存在 artifact 的 `subtitle_extraction`、`frame_pool`、`subtitle_context`、`tts` 构造测试：

- 旧 artifact 可复用时写 `workflow.stage.skipped`。
- `skip_reason=artifact_reused` 或 `checkpoint_valid`。
- 不应误写 `done status=ok`。

## 风险与降级

| 风险 | 影响 | 降级策略 |
|---|---|---|
| `subtitle_analysis` 边界在 `run_pipeline_ctx` 中不够清晰 | 难以准确计时 | 第一版包住分析调用整体，后续再拆细 |
| `polish/study/tts` 是 segment 级而非 stage 级 | 汇总字段难定义 | 先写 stage 汇总事件，细节继续用 segment 事件 |
| `subtitle_merge` 当前不是独立 stage | 无法真实 done | 先写 skipped 并记录 `not_implemented_as_separate_stage`，后续拆分产物边界 |
| 旧事件与标准事件重复 | 日志量增加 | 前端默认展示标准事件优先，旧事件保留兼容 |
| 测试断言过细导致脆弱 | 后续迭代成本高 | 第一版只断言契约字段，不断言精确顺序和完整 payload |

## 置信度更新

调研后，原方案「所有固定 stage 的 start/done/failed/skipped」的不确定性主要来自：

1. route map 中的 12 个固定 stage 与当前代码中的 5 个外层 stage 不完全一致。
2. `narration/polish/study_enrichment/tts` 是 segment 级执行，需要新增 stage 汇总事件。
3. `subtitle_merge` 需要确认是否已有独立产物边界。

通过本设计采用“标准事件并行写入 + helper + 分 milestone + 对 subtitle_merge 降级标记”的方式，第一版不需要重构管线即可落地大部分能力。

因此实现置信度从 **75%** 提升到：

- **Milestone A + B 达成 90% 左右覆盖：82%～85%**
- **包含 subtitle_merge 明确边界或文档化 skipped：80%～83%**
- **严格所有 stage 都有真实独立 run/skip 语义：仍约 70%～75%**

推荐目标定义为：**所有固定 stage 都产生标准 lifecycle 事件；暂未独立实现的 stage 可用 documented skipped reason 表达**。在这个目标下，置信度可提升到 **80% 以上**。
