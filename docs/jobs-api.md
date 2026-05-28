# Job API（文件态）

## 配置

- `JOBS_ROOT`：Job 根目录，默认 `<repo>/artifacts/jobs`
- `MAX_RUNNING_JOBS`：同时运行的 Job 数，默认 `1`
- `MOVIE_TELLER_PYTHON`：可选，指定 Python 解释器

## Job 状态 ownership

| 状态 | 写入方 | 说明 |
|------|--------|------|
| `queued` | Node | 已创建目录与 `request.json`，等待 spawn 或排队 |
| `running` | Python | `run_workflow_job` 启动时写入 |
| `succeeded` / `failed` | Python | workflow 结束 |
| `canceled` | Python（运行中取消）或 Node（未 spawn 前取消） | 终态 |
| （非状态字段）`cancel_requested_at` | Node | 已 spawn 后用户取消，仅写 `cancel.flag` + 该时间戳 |

原则：**终态由 Python 写入**（除「仍在 waiting 队列、尚未 spawn」时由 Node 直接写 `canceled`）。

Runner 日志（spawn 失败排查）：

- `{job_root}/logs/runner.stdout.log`
- `{job_root}/logs/runner.stderr.log`

若 Python 进程未正常写 manifest 即退出，Node 会将仍为 `queued`/`running` 的 Job 标为 `failed`（`error_code`: `spawn_failed` / `runner_exited`）。

## CLI

```bash
python -m movie_pipeline.job_runner \
  --job-id <uuid> \
  --jobs-root artifacts/jobs \
  --video /abs/path/to/input/source.mp4 \
  --request-json artifacts/jobs/<job_id>/request.json
```

## POST /api/jobs

`multipart/form-data`：

| 字段 | 说明 |
|------|------|
| `file` | 视频文件（必填） |
| `enablePolish` | `true` / `false` |
| `enableSpeech` | `true` / `false` |
| `enableSubtitleContext` | `true` / `false` |
| `enableEmbedVideo` | `true` / `false` |
| `forceRebuildSubtitles` | `true` / `false` |
| `forceRebuildFramePool` | `true` / `false` |
| `forceRebuildSubtitleContext` | `true` / `false` |
| `cefrLevel` | 例如 `B1` |
| `minGapSec` | 数字 |
| `subtitleGuardSec` | 数字 |
| `promptStyle` | 字符串 |
| `sourceLanguage` | 当前视频语言，传给 ASR；如 `auto` / `en` / `zh` / `ja` |
| `ttsLanguage` | TTS 语言，用于选择默认 TTS voice；如 `en` / `zh` / `ja` |
| `ttsVoice` | 可选高级覆盖，直接指定 TTS voice |
| `narrationLanguage` | 兼容字段；未传 `ttsLanguage` 时作为 TTS 语言兜底 |
| `subtitleLanguage` | 字幕语言，默认与 `sourceLanguage` 一致 |
| `userId` | 可选 |

响应 `201`：`{ jobId, status, createdAt, outputRoot }`

## 查询

- `GET /api/jobs/:jobId`
- `GET /api/jobs/:jobId/progress`
- `GET /api/jobs/:jobId/logs?limit=500&after=0` — 返回 `{ lines, truncated, nextOffset, bytesRead }`，`after` 是上一轮 `nextOffset` 字节游标；不传 `after` 时保持兼容，返回最后 `limit` 行。
- `GET /api/jobs/:jobId/artifacts`（优先读 `{job_root}/artifacts/manifest.json`）
- `GET /api/jobs/:jobId/artifacts/:kind`
- `POST /api/jobs/:jobId/cancel` — 未 spawn：返回 `{ status: "canceled" }`；已运行：返回 `{ status: "cancel_requested" }`，终态 `canceled` 由 Python 写入
- `GET /api/healthz/deep`

## 产物 manifest

成功 Job 在 Python 侧写入 `{job_root}/artifacts/manifest.json`，Node 下载 API 以该文件为单一来源（旧 Job 可回退 `workflow.json` 内 `artifacts` 字段）。
