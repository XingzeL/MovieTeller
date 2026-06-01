# Observability

落地步骤与验收见 [observability-95-landing.md](./observability-95-landing.md)。本地回归：`./scripts/run-observability-tests.sh`。

MovieTeller 的产品化主链路以 **Job** 为观测单元。一次浏览器上传会创建一个 `jobId`，后续状态、日志、进度、取消、重试与产物都围绕 `artifacts/jobs/{jobId}` 组织。

## 观测目标

阶段一可观测性的目标是：任意长视频任务卡住、失败或被取消时，可以从 Job 文件和 JSONL 日志回答以下问题：

- 当前运行到哪个固定 stage？
- 当前处理哪个 group / segment？
- 正在调用哪个 capability / provider / model / adapter？
- 调用耗时、timeout、retry 次数是多少？
- 失败是否 fatal、是否 retryable？
- 哪些 stage 是真实执行，哪些是复用 checkpoint 后 skipped？

## Job 文件布局

默认根目录为 `artifacts/jobs/{jobId}`：

```text
artifacts/jobs/<jobId>/
  workflow.json             # Job 状态机：queued/running/succeeded/failed/canceled
  request.json              # 前端请求选项
  cancel.flag               # 取消请求标记（可选）
  logs/workflow.jsonl       # 结构化事件日志
  logs/runner.stdout.log    # Python runner stdout
  logs/runner.stderr.log    # Python runner stderr
  artifacts/manifest.json   # 用户可下载产物 manifest
```

## 标准事件命名

事件名遵循 `domain.action.status`。固定 stage 生命周期统一使用：

| 事件 | 语义 |
|---|---|
| `workflow.stage.start` | stage 开始 |
| `workflow.stage.done` | stage 成功完成 |
| `workflow.stage.skipped` | stage 被显式跳过 |
| `workflow.stage.failed` | stage 失败 |

固定 stage 的生命周期**只**通过 `workflow.stage.*` 事件表达。进度聚合（`progress_from_jsonl` / `overall_progress`）与 CLI 只读取这些事件推进宏阶段；`segment.*`、`stage.group.*`、`gateway.*` 等细粒度事件仍保留。

## 固定 Stage

产品化路线图的固定 stage：

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

每个固定 stage 至少应产生：

- 一条 `workflow.stage.start`
- 一条终态事件：`workflow.stage.done` / `workflow.stage.skipped` / `workflow.stage.failed`

`skipped` 必须带 `skip_reason`。第一版允许的原因：

- `disabled_by_request`
- `artifact_reused`
- `checkpoint_valid`
- `not_requested`
- `no_segments`
- `no_output_requested`
- `not_implemented_as_separate_stage`

## Stage 字段契约

### Start

```json
{
  "event": "workflow.stage.start",
  "stage": "tts",
  "status": "start",
  "job_id": "...",
  "x_output_root": "..."
}
```

推荐字段：`stage_index`、`stage_total`、`input_path`、`input_count`、`enabled`、`force_rebuild`。

### Done

```json
{
  "event": "workflow.stage.done",
  "stage": "tts",
  "status": "ok",
  "duration_ms": 1234,
  "segment_count": 12
}
```

### Skipped

```json
{
  "event": "workflow.stage.skipped",
  "stage": "tts",
  "status": "skipped",
  "duration_ms": 12,
  "skip_reason": "disabled_by_request"
}
```

### Failed

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

## Gateway 字段契约

Gateway 事件包括：

- `gateway.chat.start/done/failed`
- `gateway.embedding.start/done/failed`
- `gateway.speech.start/done/failed`

统一字段：

| 字段 | 说明 |
|---|---|
| `capability` | `narration` / `polish` / `study_enrichment` / `tts` / `embedding` / `chat` |
| `provider` | provider 名称 |
| `model` | 模型名 |
| `adapter` | adapter 名称 |
| `timeout_sec` | 本次调用 timeout |
| `duration_ms` | 调用总耗时，包含 retry |
| `retry_count` | 已发生的重试次数 |
| `max_attempts` | 最大尝试次数 |
| `error_code` | 标准错误码，失败时必填 |
| `retryable` | 是否可重试 |
| `fatal` | 是否导致主流程失败 |

## 排障 Cookbook

### 查看 Job 状态

```bash
cat artifacts/jobs/<jobId>/workflow.json | jq .
```

### 查看当前 stage

```bash
cat artifacts/jobs/<jobId>/logs/workflow.jsonl \
  | jq -r 'select(.event | startswith("workflow.stage.")) | [.ts,.event,.stage,.status,.skip_reason,.duration_ms] | @tsv'
```

### 查看失败原因

```bash
cat artifacts/jobs/<jobId>/logs/workflow.jsonl \
  | jq 'select(.event == "workflow.stage.failed" or (.event | endswith(".failed")))'
```

### 查看 gateway 慢调用或重试

```bash
cat artifacts/jobs/<jobId>/logs/workflow.jsonl \
  | jq 'select(.event | startswith("gateway.")) | {ts,event,capability,provider,model,timeout_sec,duration_ms,retry_count,error_code}'
```

### 查看取消是否生效

```bash
ls artifacts/jobs/<jobId>/cancel.flag
cat artifacts/jobs/<jobId>/workflow.json | jq '{status, cancel_requested_at, error}'
```

注意：取消是协作式的。若 Python 正阻塞在 ASR / LLM / TTS / ffmpeg 调用内部，需要等该调用返回或 timeout 后，下一次 cancel check 才能写入 `canceled`。

## 前端展示建议

若后续恢复前端日志面板，应优先突出：

- `workflow.stage.failed`
- `gateway.*.failed`
- `status=warning`
- 当前最新 `workflow.stage.start`
- 所有 `workflow.stage.skipped` 及其 `skip_reason`

普通 segment 事件可折叠展示，避免长视频日志淹没关键错误。
