# MovieTeller Public Deployment Architecture

## Goal

将当前本地可运行的处理链：

- `subtitle_extraction`
- `subtitle_analysis`
- `narration`

升级为可上线公网的服务端视频处理系统。

目标能力：

1. 用户在公网产品中上传视频
2. 视频在服务器侧异步处理
3. 服务器提取字幕、分析无字幕片段、生成旁白脚本
4. 前端可以查询任务进度和结果
5. 系统支持并发、失败重试、限流、成本控制

---

## Current State

当前仓库已经有可复用的核心 Python 能力：

- `python/subtitle_extraction`
  - 调 `videocaptioner transcribe`
  - 输出 `.srt` 和结构化 `cues`
- `python/subtitle_analysis`
  - 从 `.srt` 计算字幕覆盖区间
  - 推断无字幕区间
  - 可直接调用 `narration` 输出带时间轴的旁白 JSON
- `python/narration`
  - 对指定视频时间段抽帧
  - 调多模态模型生成旁白

这些模块本身可以保留，公网化时主要调整的是服务编排，而不是重写算法模块。

---

## Recommended Architecture

推荐拆成 5 个逻辑组件：

1. `Web API`
2. `Object Storage`
3. `Job Queue`
4. `Worker`
5. `Database`

建议拓扑：

```text
Browser / App
    |
    v
Web API (Node/Express)
    | \
    |  \--> Database
    |
    +--> Object Storage
    |
    +--> Job Queue
             |
             v
         Worker (Python pipeline runtime)
             | \
             |  \--> Object Storage
             \----> Database
```

---

## Responsibilities

### 1. Web API

职责：

- 用户鉴权
- 创建任务
- 下发上传地址
- 查询任务状态
- 返回处理结果

不要做的事：

- 不要在请求线程内同步跑完整视频处理
- 不要在 API 进程内直接承载长时间 CPU / ffmpeg / ASR 工作

建议继续用当前 Node/Express 作为 API 层。

### 2. Object Storage

建议用：

- AWS S3
- 阿里云 OSS
- 腾讯云 COS

职责：

- 存原始视频
- 存导出的 `.srt`
- 存旁白脚本 JSON
- 可选存中间结果，如关键帧、调试日志

不要依赖本机 `/tmp` 作为最终数据存储。

### 3. Job Queue

建议选型：

- Redis + BullMQ
- AWS SQS
- RabbitMQ

如果你希望 Node API 保持简单，优先建议：

- `Redis + BullMQ`

原因：

- 和 Node 集成简单
- 有延时、重试、并发控制
- 本地开发方便

### 4. Worker

职责：

- 从队列消费任务
- 下载视频到本地临时目录
- 跑 `subtitle_extraction`
- 跑 `subtitle_analysis`
- 跑 `narration`
- 上传结果回对象存储
- 更新数据库任务状态

建议 Worker 使用容器运行，镜像内预装：

- Python 3.12
- ffmpeg / ffprobe
- `videocaptioner`
- `movieteller_config`
- `subtitle_extraction`
- `subtitle_analysis`
- `narration`

结论：

- 开发环境可以继续用 `.venv`
- 生产环境应使用 Docker 镜像，不依赖仓库本地 `.venv`

### 5. Database

建议选型：

- PostgreSQL

职责：

- 存任务元信息
- 存状态机
- 存结果索引
- 存错误原因
- 存用户和配额

---

## Request Flow

推荐把公网处理流程拆成 3 个阶段。

### Phase A: Upload

1. 前端请求 `POST /api/jobs`
2. API 创建数据库记录，状态为 `created`
3. API 返回：
   - `jobId`
   - 预签名上传 URL
   - 对象存储 key
4. 前端直接把视频上传到对象存储

这样能避免大文件先打满 API 服务器带宽。

### Phase B: Enqueue

上传完成后：

1. 前端调用 `POST /api/jobs/:id/submit`
2. API 校验上传对象存在
3. API 将任务写入队列
4. 数据库状态改为 `queued`

### Phase C: Process

Worker 消费任务：

1. 状态改为 `running`
2. 下载视频到本地工作目录
3. 运行字幕提取
4. 运行字幕分析
5. 运行旁白生成
6. 上传结果 JSON / SRT 到对象存储
7. 数据库状态改为 `completed`

失败时：

1. 记录错误信息
2. 更新状态为 `failed`
3. 按规则重试或终止

---

## Worker Internal Pipeline

每个任务内部建议统一走一个 Python 入口，而不是让 Node 分别拼多个 `spawn`。

推荐新增一个 Python 级总入口，例如：

- `python/pipeline_runner`

或者先直接复用：

- `python -m subtitle_analysis --narrate --json`

推荐 Worker 内部步骤：

1. 输入：
   - `video_path`
   - `min_gap_sec`
   - `subtitle_guard_sec`
   - `max_candidates`
   - `provider`
   - `model`
2. 调 `subtitle_extraction`
3. 得到 `.srt`
4. 调 `subtitle_analysis`
5. 得到 `narrationCandidates`
6. 调 `narration`
7. 输出结构：
   - `subtitlePath`
   - `subtitleSpans`
   - `rawGaps`
   - `narrationCandidates`
   - `narratedSegments`

生产里建议把这一步封成 Worker 内部 Python 函数或单独 CLI，减少跨语言拼接复杂度。

---

## API Design

建议的公网接口如下。

### `POST /api/jobs`

用途：

- 创建视频处理任务

请求体：

```json
{
  "filename": "demo.mp4",
  "contentType": "video/mp4",
  "sizeBytes": 3147315,
  "options": {
    "minGapSec": 1.5,
    "subtitleGuardSec": 0.25,
    "maxCandidates": 3,
    "promptStyle": "documentary",
    "provider": "volcengine",
    "model": null
  }
}
```

响应体：

```json
{
  "jobId": "job_123",
  "uploadUrl": "https://...",
  "objectKey": "uploads/user_1/job_123/source.mp4"
}
```

### `POST /api/jobs/:jobId/submit`

用途：

- 告诉服务端上传已完成，可以入队

响应体：

```json
{
  "jobId": "job_123",
  "status": "queued"
}
```

### `GET /api/jobs/:jobId`

用途：

- 查询任务状态和结果

响应体示例：

```json
{
  "jobId": "job_123",
  "status": "completed",
  "progress": 100,
  "result": {
    "subtitleJsonUrl": "https://...",
    "subtitleSrtUrl": "https://...",
    "narrationJsonUrl": "https://..."
  },
  "error": null
}
```

### `GET /api/jobs/:jobId/result`

用途：

- 返回最终聚合结果

可直接返回：

- `subtitleSpans`
- `rawGaps`
- `narrationCandidates`
- `narratedSegments`

---

## Database Schema

建议至少有两张表。

### `video_jobs`

字段建议：

- `id`
- `user_id`
- `status`
- `source_object_key`
- `source_filename`
- `source_content_type`
- `source_size_bytes`
- `min_gap_sec`
- `subtitle_guard_sec`
- `max_candidates`
- `prompt_style`
- `provider_slug`
- `model_id`
- `progress`
- `error_code`
- `error_message`
- `result_object_key`
- `subtitle_srt_object_key`
- `created_at`
- `queued_at`
- `started_at`
- `finished_at`

### `job_events`

字段建议：

- `id`
- `job_id`
- `event_type`
- `message`
- `payload_json`
- `created_at`

作用：

- 记录状态流转
- 调试失败
- 前端展示阶段进度

---

## Status Machine

建议状态机：

- `created`
- `uploading`
- `uploaded`
- `queued`
- `running`
- `extracting_subtitles`
- `analyzing_subtitles`
- `generating_narration`
- `uploading_results`
- `completed`
- `failed`
- `cancelled`

最小版本可以只保留：

- `created`
- `queued`
- `running`
- `completed`
- `failed`

但如果要公网产品可观测，建议保留阶段状态。

---

## Result Format

最终结果建议以 JSON 文件形式落对象存储，例如：

```json
{
  "jobId": "job_123",
  "videoDurationSec": 115.378345,
  "subtitleSpans": [],
  "rawGaps": [],
  "narrationCandidates": [],
  "narratedSegments": [
    {
      "startSec": 4.61,
      "endSec": 7.33,
      "durationSec": 2.72,
      "text": "A young girl in a pink dress stands outside...",
      "prevSubtitleText": "我不要和成绩差的人说话",
      "nextSubtitleText": "哇",
      "timingExtractSec": 0.30,
      "timingApiSec": 2.44,
      "timingTotalSec": 2.74,
      "frameCount": 24
    }
  ]
}
```

这个格式已经和当前 `subtitle_analysis --narrate --json` 的输出方向一致，可以直接复用。

---

## Runtime Packaging

### Development

继续使用：

- 项目根目录 `.venv`

### Production

必须改成镜像打包。

建议 Dockerfile 包含：

- Python 3.12
- ffmpeg
- 系统依赖
- `videocaptioner`
- 项目 Python 包

不要在生产服务器上靠手工 `pip install` 或路径约定拼环境。

---

## Security

公网必须补这些能力：

### Upload Security

- 只允许已登录用户创建任务
- 限制 MIME type
- 限制文件大小
- 限制单用户并发上传数

### Access Control

- 结果对象 key 按用户命名空间隔离
- 下载结果时做鉴权
- 不直接暴露裸对象存储路径

### Content Safety

- 需要时加入视频内容审核
- 需要时对文本输出做审查

### Secret Management

- 模型 API Key 不存仓库 `.env`
- 生产用 KMS / Secret Manager / 环境密钥注入

---

## Cost Control

公网产品必须有成本阀门。

建议加这些限制：

- 单视频最大时长
- 单视频最大文件大小
- `maxCandidates` 上限
- `max_frames_per_segment` 上限
- 每用户每日任务数上限
- 每用户每日总视频时长上限

Worker 执行时还建议：

- 超过阈值直接失败
- 长视频可先分段或降级
- 可选只生成前 `N` 个候选片段的旁白

---

## Retry and Failure Handling

失败分 3 类处理：

### 可重试

- 对象存储下载失败
- 模型 API 短暂超时
- 网络抖动

策略：

- 指数退避
- 最多重试 2 到 3 次

### 不可重试

- 视频格式不支持
- `ffmpeg` 无法解码
- 字幕提取命令参数错误

策略：

- 直接标记 `failed`

### 部分成功

- 字幕提取成功
- 旁白生成部分片段失败

策略：

- 仍输出 `subtitleSpans` / `rawGaps`
- `narratedSegments` 中只保留成功项
- 失败项单独带错误字段

---

## Observability

建议最少落这些日志和指标。

### Logs

- `job_id`
- `user_id`
- 阶段名
- 输入视频时长
- 字幕条数
- gap 数量
- 实际旁白生成段数
- 每段耗时
- 错误堆栈

### Metrics

- 任务总数
- 成功率
- 平均处理耗时
- 每阶段耗时
- 平均视频时长
- 平均候选片段数
- 每 provider 模型调用量

### Tracing

如果后面要上规模，建议接：

- OpenTelemetry

---

## Suggested Implementation Order

### Phase 1: Internal Async Version

- 仍部署在单台服务器
- 引入 Redis + BullMQ
- Node API 创建任务
- Worker 本机跑 Python pipeline
- 结果先存数据库或本地对象存储替代

目标：

- 验证异步编排

### Phase 2: Object Storage + Real Worker

- 上传改为预签名直传对象存储
- Worker 从对象存储拉视频
- 结果回写对象存储

目标：

- 脱离单机临时文件依赖

### Phase 3: Containerized Production

- Worker 容器化
- API 容器化
- 分离部署
- 引入监控、告警、限流

目标：

- 支持公网稳定运行

---

## Recommended Immediate Changes In This Repository

如果按这个方案推进，仓库里下一步建议做这些具体改动：

1. 在 `server` 新增异步任务 API，而不是扩展当前同步 `extract` 路由
2. 新增共享 Python runtime helper，统一 Worker / Node 调 Python 的方式
3. 在 Python 侧新增单一“pipeline runner”入口，减少 Node 拼命令逻辑
4. 明确最终结果 JSON schema，并固定下来给前端使用
5. 补一套面向任务处理的集成测试

---

## Final Recommendation

结论很明确：

- 核心 Python 模块可以保留
- Node 仍适合做 API 网关
- 但公网产品必须引入异步任务、对象存储、数据库、Worker

也就是说：

- 当前代码适合作为“处理引擎”
- 还需要再加一层“生产级任务系统”

这是从本地原型走向公网部署的正确演进路径。
