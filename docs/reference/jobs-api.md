# Job API（文件态）

**生命周期、ACL、410、列表与 retention 产品决策**见 **[job-lifecycle.md](job-lifecycle.md)**（合同优先于本文档的简述）。

本地如何启动前后端、Job 目录布局与排障见 **[local-development.md](local-development.md)**。

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
| `sourceLanguage` | 当前视频语言，传给 ASR；如 `auto` / `en` / `zh` / `ja` / `vi` |
| `ttsLanguage` | TTS 语言，用于旁白与 TTS；如 `en` / `zh` / `ja` / `vi` |
| `ttsVoice` | 可选高级覆盖，直接指定 TTS voice |
| `narrationLanguage` | 兼容字段；未传 `ttsLanguage` 时作为 TTS 语言兜底 |
| `subtitleLanguage` | 字幕语言，默认与 `sourceLanguage` 一致 |
| `userId` | 可选 |

响应 `201`：`{ jobId, status, createdAt, outputRoot }`

上传校验（`400`）：

- 扩展名须为 `.mp4`、`.mov`、`.mkv`、`.webm`、`.m4v` 之一
- `Content-Type` 须为常见 `video/*` 或 `application/octet-stream`
- 单文件最大 **500MB**（multer `limits.fileSize`）

## 查询

- `GET /api/jobs?limit=20&offset=0` — 按 `updated_at`（缺省则 `created_at`）**降序**分页；返回 `{ jobs, total, limit, offset }`。列表项含 `videoState`、`canDownloadVideo`、`canOpenStudyCards` 等。`limit` 默认 20、**最大 1000**（产品决策见 [job-lifecycle.md § List and retention](job-lifecycle.md)）。
- `GET /api/jobs/:jobId`
- `GET /api/jobs/:jobId/progress`
- `GET /api/jobs/:jobId/logs?limit=500&after=0` — 返回 `{ lines, truncated, nextOffset, bytesRead }`，`after` 是上一轮 `nextOffset` 字节游标；不传 `after` 时保持兼容，返回最后 `limit` 行。
- `GET /api/jobs/:jobId/artifacts`（读取 `{job_root}/artifacts/manifest.json`）
- `GET /api/jobs/:jobId/artifacts/:kind`
- `POST /api/jobs/:jobId/cancel` — 未 spawn：返回 `{ status: "canceled" }`；已运行：返回 `{ status: "cancel_requested" }`，终态 `canceled` 由 Python 写入（时序与检查点见 [local-development.md §10](local-development.md#10-取消语义与信号生效)）
- `POST /api/jobs/:jobId/retry` — 仅 `failed` / `canceled`；在同一 Job 目录上重新入队（保留 artifact，依赖 Python stage resume）。返回 `{ jobId, status: "queued", retriedAt }`；`409` 若已在运行或状态不可重试
- `GET /api/healthz/deep`

## 产物 manifest

成功 Job 在 Python 侧写入 `{job_root}/artifacts/manifest.json`，Node 下载 API 以该文件为单一来源；不再回退读取旧 Job 的 `workflow.json.artifacts` 字段。

对用户暴露的下载类型仅两种：

| kind | 说明 |
|------|------|
| `renderedVideo` | 旁白成片（`render/narrated.mp4`） |
| `studyCardsHtml` | 学习卡片 HTML |

Web 前端创建 Job 时固定 `enablePolish=true`、`enableSubtitleContext=true`（默认开启，不提供勾选框）。仅 **TTS** 等少数选项暴露给用户。

## Smoke 测试（HTTP）

需先启动 `cd server && npm run dev`。在另一终端：

```bash
# 默认：健康检查、列表、404、上传校验（不跑完整 workflow）
cd server && npm run smoke

# 创建 Job 并验证列表 / 详情 / logs 游标（需 ffmpeg 或 --video=）
npm run smoke:create

# 创建后取消并轮询至 canceled（需 runner，比 workflow 轻）
npm run smoke:cancel

# 轮询至终态；成功时检查 artifacts（耗时长，需 Python/API 配置就绪）
npm run smoke:workflow
# 全栈门禁（必须 succeeded）：
node ../scripts/jobs-api-smoke.mjs --mode=workflow --strict --video=/path/to/clip.mp4 --timeout-sec=900

# 脚本逻辑单测（无需 server）
npm run smoke:unit
```

环境变量：`MOVIE_TELLER_BASE_URL`、`MOVIE_TELLER_SMOKE_MODE`、`MOVIE_TELLER_SMOKE_VIDEO`、`MOVIE_TELLER_SMOKE_TIMEOUT_SEC`、`MOVIE_TELLER_SMOKE_STRICT=1`。

详见 [jobs-api-smoke.md](jobs-api-smoke.md)（置信度与模式说明）。
