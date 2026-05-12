# MovieTeller API + Worker + Queue Refactor Plan

## Purpose

这份文档基于当前仓库结构，给出直接可执行的代码改造清单。

目标：

- 保留现有 Python 处理模块
- 保留 Node 作为 API 层
- 在仓库内加入：
  - 异步任务 API
  - 队列生产者
  - Worker 消费者
  - 统一 Python pipeline 调用入口

---

## Current Relevant Code

当前已有的关键代码：

- API server 入口
  - [server/src/index.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/index.js)
- 字幕提取 HTTP 路由
  - [server/src/routes/extract.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/routes/extract.js)
- Python 运行时封装
  - [server/src/services/extraction/runSubtitleExtraction.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/services/extraction/runSubtitleExtraction.js)
- 字幕提取 Python 包
  - [python/subtitle_extraction](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_extraction)
- 字幕分析 Python 包
  - [python/subtitle_analysis](/Users/zhuanz0000/WorkSpace/MovieTeller/python/subtitle_analysis)
- 旁白生成 Python 包
  - [python/narration](/Users/zhuanz0000/WorkSpace/MovieTeller/python/narration)

---

## Refactor Strategy

不要把新能力硬塞进现有 `/api/extract/subtitles`。

建议新增一条并行链路：

- `POST /api/jobs`
- `POST /api/jobs/:id/submit`
- `GET /api/jobs/:id`
- `GET /api/jobs/:id/result`

并新增一个后台 Worker 入口。

---

## Proposed Directory Changes

建议新增以下文件。

### API Layer

- `server/src/routes/jobs.js`
- `server/src/services/jobs/createJob.js`
- `server/src/services/jobs/submitJob.js`
- `server/src/services/jobs/getJob.js`
- `server/src/services/jobs/getJobResult.js`

### Queue Layer

- `server/src/queue/index.js`
- `server/src/queue/jobNames.js`
- `server/src/queue/enqueueVideoJob.js`

### Shared Runtime Helpers

- `server/src/services/pythonRuntime.js`

把现有 [runSubtitleExtraction.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/services/extraction/runSubtitleExtraction.js) 中可复用的 Python 环境逻辑抽到这里。

### Worker Layer

- `worker/src/index.js`
- `worker/src/queue/index.js`
- `worker/src/handlers/processVideoJob.js`
- `worker/src/services/storage/downloadObject.js`
- `worker/src/services/storage/uploadObject.js`
- `worker/src/services/python/runPipeline.js`

### Database / Migrations

- `server/db/migrations/001_create_video_jobs.sql`
- `server/db/migrations/002_create_job_events.sql`

### Optional Python Aggregation Entry

如果你希望减少 Node 侧拼 Python 命令的复杂度，建议新增：

- `python/pipeline_runner/pyproject.toml`
- `python/pipeline_runner/src/pipeline_runner/__main__.py`

它可以统一包装：

- `subtitle_extraction`
- `movie_pipeline`

---

## Step 1: Extract Shared Python Runtime Helper

### Why

现在 [runSubtitleExtraction.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/services/extraction/runSubtitleExtraction.js) 已经能：

- 优先命中项目 `.venv/bin/python3`
- 给子进程设置 `PYTHONPATH`
- prepend `.venv/bin` 到 `PATH`

这部分将来：

- 字幕提取要用
- subtitle_analysis pipeline 要用
- Worker 也要用

所以必须抽成共享 helper。

### New File

- `server/src/services/pythonRuntime.js`

### Exported Functions

- `resolveProjectPython(repoRoot, explicitPython)`
- `buildPythonEnv(repoRoot, extraPythonPaths = [])`
- `spawnPythonModule({ moduleName, args, cwd, repoRoot, pythonExe })`

### Existing File To Refactor

- [server/src/services/extraction/runSubtitleExtraction.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/services/extraction/runSubtitleExtraction.js)

改为依赖共享 helper，而不是自己维护解析逻辑。

---

## Step 2: Add Job APIs

### New Route

- `server/src/routes/jobs.js`

### Required Handlers

#### `POST /api/jobs`

职责：

- 校验登录态
- 校验请求参数
- 插入 `video_jobs`
- 生成对象存储上传地址

#### `POST /api/jobs/:id/submit`

职责：

- 校验任务归属
- 校验对象已上传
- 更新状态为 `queued`
- 调 `enqueueVideoJob(jobId)`

#### `GET /api/jobs/:id`

职责：

- 返回状态、进度、错误、结果地址

#### `GET /api/jobs/:id/result`

职责：

- 返回已经落对象存储或数据库的最终 JSON 内容

### Existing File To Update

- [server/src/index.js](/Users/zhuanz0000/WorkSpace/MovieTeller/server/src/index.js)

需要挂载新的 `jobsRouter`。

---

## Step 3: Add Queue Producer

### New Files

- `server/src/queue/index.js`
- `server/src/queue/jobNames.js`
- `server/src/queue/enqueueVideoJob.js`

### Responsibility

统一定义队列名和 job payload。

### Recommended Payload

```json
{
  "jobId": "job_123"
}
```

不要把太多大对象塞进队列。Worker 自己通过 `jobId` 去数据库查完整参数。

---

## Step 4: Add Worker App

### New App

- `worker/src/index.js`

职责：

- 连接队列
- 注册 `processVideoJob`
- 控制并发数

### New Handler

- `worker/src/handlers/processVideoJob.js`

职责：

1. 从数据库读取任务配置
2. 更新状态为 `running`
3. 下载对象存储中的原始视频
4. 跑 Python pipeline
5. 上传结果文件
6. 更新数据库状态为 `completed`
7. 捕获异常并更新为 `failed`

---

## Step 5: Define Worker Internal Stages

建议 `processVideoJob` 内部严格分阶段：

1. `downloading_source`
2. `extracting_subtitles`
3. `analyzing_subtitles`
4. `generating_narration`
5. `uploading_results`
6. `completed`

每个阶段都：

- 更新 `video_jobs.status`
- 写一条 `job_events`

这样前端就能显示真实进度。

---

## Step 6: Python Pipeline Invocation

### Option A: Directly Reuse `movie_pipeline`

Worker 里直接执行：

```bash
python -m subtitle_extraction ...
python -m movie_pipeline --json ...
```

优点：

- 改动小

缺点：

- Node / Worker 侧要管理两次命令调用和中间 `.srt`

### Option B: Add Aggregated Python Entry

新增：

- `python/pipeline_runner`

统一执行：

```bash
python -m pipeline_runner \
  --video /tmp/source.mp4 \
  --min-gap-sec 1.5 \
  --subtitle-guard-sec 0.25 \
  --max-candidates 3 \
  --json
```

推荐长期走这个方案。

优点：

- Worker 只调一次 Python
- 中间细节都留在 Python 内部
- 更利于后续本地和生产共用一套 pipeline

---

## Step 7: Result Storage Design

Worker 完成后，建议上传这些对象：

- `source.mp4`
- `subtitles/result.srt`
- `results/final.json`

数据库里只存：

- `source_object_key`
- `subtitle_srt_object_key`
- `result_object_key`

不要把大 JSON 或大字幕全文都直接塞数据库正文列，最小版可以存索引。

---

## Step 8: Database Changes

### Table `video_jobs`

最少字段：

- `id`
- `user_id`
- `status`
- `progress`
- `source_object_key`
- `result_object_key`
- `subtitle_srt_object_key`
- `min_gap_sec`
- `subtitle_guard_sec`
- `max_candidates`
- `prompt_style`
- `provider_slug`
- `model_id`
- `error_code`
- `error_message`
- `created_at`
- `queued_at`
- `started_at`
- `finished_at`

### Table `job_events`

最少字段：

- `id`
- `job_id`
- `event_type`
- `message`
- `payload_json`
- `created_at`

---

## Step 9: Frontend Contract

前端至少要改两处。

### Upload Flow

从“直接打同步接口”改成：

1. 创建 job
2. 上传视频
3. submit job
4. 轮询 job 状态

### Result Page

展示：

- 任务状态
- 字幕覆盖区间
- 无字幕候选区间
- 已生成旁白段

重点消费字段：

- `narratedSegments`

---

## Step 10: Config and Secret Changes

### Server/API

新增环境变量建议：

- `DATABASE_URL`
- `REDIS_URL`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_REGION`
- `OBJECT_STORAGE_ACCESS_KEY`
- `OBJECT_STORAGE_SECRET_KEY`

### Worker

新增环境变量建议：

- `DATABASE_URL`
- `REDIS_URL`
- `OBJECT_STORAGE_BUCKET`
- `MOVIE_TELLER_CONFIG`
- 模型 provider 相关 API Key

### Keep

现有：

- `VIDEOCAPTIONER_*`
- `NARRATION_PROVIDER`
- `API_KEYS_JSON`
- `API_BASE_URLS_JSON`

这些配置模型仍然可以保留。

---

## Step 11: Deployment Split

推荐至少拆成两个 deployable：

### `api-server`

包含：

- Express API
- Queue producer
- DB access

### `worker`

包含：

- Queue consumer
- Python runtime
- ffmpeg
- `videocaptioner`

不要把两者塞进同一个长期运行进程里。

---

## Step 12: Minimal Milestone Order

建议按下面顺序做，不要并行乱改。

### Milestone 1

- 抽 `pythonRuntime.js`
- 保持现有同步接口不坏

### Milestone 2

- 增加 `jobs` API
- 增加数据库表
- 增加队列 producer

### Milestone 3

- 增加 Worker
- Worker 能把假任务从队列取出并改状态

### Milestone 4

- Worker 跑真实 Python pipeline
- 结果回写数据库 / 文件

### Milestone 5

- 接对象存储
- 完成端到端上传 -> 结果返回

### Milestone 6

- 前端接入真实任务流

---

## Suggested First PR Breakdown

为了降低改动风险，建议拆 PR。

### PR 1

- 新增 `server/src/services/pythonRuntime.js`
- 重构 `runSubtitleExtraction.js`

### PR 2

- 新增数据库迁移
- 新增 `jobs` API 空壳

### PR 3

- 新增队列层
- 新增 Worker 空壳

### PR 4

- Worker 接 `movie_pipeline`
- 打通真实 pipeline

### PR 5

- 接对象存储
- 接前端任务轮询

---

## High-Risk Areas

这些是改造时最容易踩坑的地方：

### 1. Python Environment Drift

开发用 `.venv`，生产用容器镜像。不要把开发路径约定直接搬到生产。

### 2. Long Task Timeout

公网 HTTP 请求不能承载完整处理时间，必须异步。

### 3. Large File Handling

不要让 API 进程充当视频流中转。

### 4. Output Contract Drift

先冻结 JSON schema，再改前后端。

### 5. Partial Failures

字幕提取成功但旁白失败时，任务不一定要整单报废。

---

## Recommended Immediate Next Change In Repo

如果按工程价值排序，当前仓库里最应该先做的是：

1. 抽 `server/src/services/pythonRuntime.js`
2. 新增 `jobs` 路由骨架
3. 新增 Worker 骨架
4. 新增一个统一 Python pipeline runner

这 4 步完成后，整个异步架构就有稳定骨架了。
