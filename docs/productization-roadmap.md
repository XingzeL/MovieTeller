# MovieTeller 产品化阶段流程

本文档描述 MovieTeller 从当前手动脚本/本地管线，演进到可由前端调用、可观测、可恢复、可运营的产品化视频处理系统的阶段计划。

**当前已可用的本地主链路**（上传 → Job API → Python runner）见 [local-development.md](./local-development.md) 与 [jobs-api.md](./jobs-api.md)。**Smoke 分层、`--strict` 与 CI 常态化**见下文 [质量门禁、Smoke 测试与 CI](#质量门禁smoke-测试与-ci)。

核心原则：

- 做减法：先固定边界和主链路，不同时引入过多兼容分支。
- Job 化：一次视频处理就是一个 Job，所有状态、日志、产物都围绕 Job 组织。
- 可恢复：长视频失败后不能从头重跑，阶段产物必须可复用。
- 可观测：每个阶段、每个模型调用、每个 segment 都要能定位状态。
- 可降级：非核心增强能力失败时不应拖垮整个视频主流程。

## 目标架构

```text
Frontend
  -> POST /jobs WorkflowRequest
  -> API / Job Creator
  -> Settings Loader
  -> Policy Resolver
  -> ResolvedRunContext
  -> Job Runner
  -> Workflow Stages
  -> Artifacts + Logs + Job Status
  -> Frontend Polling / Event Stream
```

最终调用链：

```text
WorkflowRequest
  -> Settings
  -> PolicyContext
  -> ResolvedWorkflowConfig
  -> ResolvedRunContext
  -> run_full_workflow(ctx)
```

前端不直接感知内部 `Settings`、模型 slug、provider、key 池、pipeline options。功能模块也不关心模型和 provider。

## 阶段一：日志与可观测性收口

目标：先解决“长视频跑到哪里、卡在哪里、哪个 API 出错”的问题。

任务清单：

- 修复 `ContextVar` 在线程池中的上下文传播，确保 `job_id`、`group_index`、`segment_index` 在并行 worker 中完整保留。
- 将日志初始化从中层 pipeline 上移到 workflow/job 入口，底层模块只负责 `emit_event()`。
- 为每个 Job 生成独立日志文件，例如 `artifacts/{job_id}/logs/workflow.jsonl`。当前已支持未显式配置 `logging.file` 时默认写到 `{output_root}/logs/workflow.jsonl`。
- 在 Job 结束、失败、取消时显式 flush/shutdown 日志队列。
- 统一事件命名为 `domain.action.status`，例如 `gateway.chat.start`、`segment.study.failed`。
- 补齐关键阶段日志：subtitle extraction、subtitle analysis、frame pool、narration、polish、study enrichment、tts、subtitle merge、render、export。
- 将现有 `print()` 型调试输出逐步替换为结构化日志。

验收标准：

- 任意长视频任务可以通过 JSONL 日志看出当前阶段、当前 segment、当前模型调用。
- NewAPI / TTS 卡住或返回 500 时，可以定位到 capability、provider、model、segment。
- 并行执行时日志不交错、不丢失上下文。

### 可观测性 95% 收口（已落地）

实现说明见 [observability-95-landing.md](./observability-95-landing.md)、[observability.md](./observability.md)。

| 能力 | 说明 |
|------|------|
| 宏阶段事件 | 仅 `workflow.stage.start/done/skipped/failed`，覆盖 `FIXED_WORKFLOW_STAGES` |
| 进度聚合 | `progress_from_jsonl` / `overall_progress` 宏阶段与 `x_*` artifact 只读 `workflow.stage.*` |
| 注册表 | `stage_registry` 宏 ID：`render`、`export`；固定 stage 别名映射至宏权重 |
| 回归 | `./scripts/run-observability-tests.sh`；CI：`.github/workflows/python-observability.yml` |

本地门禁：

```bash
./scripts/run-observability-tests.sh
```

## 阶段二：Job 模型与产物目录标准化

目标：把一次视频处理从“脚本运行”变成“可追踪 Job”。

Job 基础字段：

```text
job_id
user_id
status
input_video_path
output_root
current_stage
progress
created_at
updated_at
error
artifacts
```

Job 状态：

```text
queued
running
succeeded
failed
canceled
```

标准目录：

```text
artifacts/{job_id}/
  input/
  logs/workflow.jsonl
  subtitles/extracted.srt
  subtitles/final.subtitled.srt
  analysis/subtitle_analysis.json
  frame_pool/manifest.jsonl
  narration/narration.json
  speech/speech_video.json
  speech/audio/*.mp3
  render/narrated.mp4
  study_cards/study_cards.html
  workflow.json
```

任务清单：

- 定义 `JobRecord` 数据结构。已落地为 `movie_pipeline.job.JobRecord`，先保持内存/JSON 形态，不引入数据库。
- 定义 `JobPaths` 标准目录布局。已落地为 `movie_pipeline.job.JobPaths`，先只提供路径解析和目录创建，不接管现有 workflow 输出。
- 定义 `WorkflowArtifacts` 数据结构。已落地为 `movie_pipeline.job.WorkflowArtifacts`，与现有 `workflowArtifacts` payload camelCase 字段保持等价互转。
- 统一 output root 生成规则。
- 写出 `workflow.json` Job manifest。已落地为 `write_job_record/read_job_record`，`run_full_workflow` 成功和失败都会写出当前 JobRecord。
- 提供轻量 Job 执行入口。已落地为 `movie_pipeline.job_runner.run_workflow_job`，负责把 `job_id + jobs_root + video_path` 绑定成 `WorkflowRequest/ResolvedRunContext`，再复用 `run_full_workflow`；暂不引入 HTTP、队列或数据库。
- 建立文件态 Job 状态闭环。已落地为 `movie_pipeline.job.JobStore`，runner 启动前先写 `running`，结束状态继续由 `run_full_workflow` 写 `succeeded/failed`，API 层可直接读取 `{job_root}/workflow.json`。
- 每个 stage 只写自己的 artifact，不跨阶段隐式修改别人的文件。
- manual script 只作为 smoke test，不再承担主入口职责。

验收标准：

- 一个 Job 的所有产物都能从 `job_id` 定位。
- 产物文件命名稳定，前端和 API 不需要猜路径。
- 失败 Job 也保留已经完成的中间产物。

## 阶段三：WorkflowRequest 与配置解析链路

目标：前端只提交业务请求，服务端负责解析成可执行上下文。

前端请求示例：

```json
{
  "videoId": "video_123",
  "workflow": "narrated_video",
  "options": {
    "enablePolish": true,
    "enableSpeech": true,
    "enableStudyCards": true,
    "subtitleOutputMode": "burn_in"
  }
}
```

服务端解析链路：

```text
WorkflowRequest
  + Settings
  + UserInfo
  -> PolicyContext
  -> ResolvedWorkflowConfig
  -> ResolvedRunContext
```

职责边界：

- `Settings`：静态部署配置，例如 provider、base_url、默认模型、ffmpeg、默认并发。
- `WorkflowRequest`：本次任务的业务意图，例如是否生成 TTS、是否导出学习卡。
- `PolicyContext`：用户等级、额度、权限、可用模型、可用并发。
- `ResolvedRunContext`：唯一传入 workflow 的运行时上下文。

任务清单：

- 定义 `WorkflowRequest`。
- 定义 `PolicyContext`。
- 定义 resolver，将 request/settings/policy 合成为 `ResolvedRunContext`。
- 收口 `run_full_workflow()` 调用形式，最终只传 `ctx`。
- 提供服务端 Job 入口。已落地为 `build_job_request/run_workflow_job`，调用方不再手动拼 `output_root/workspace_id`。
- 移除重复 option 对象和历史兼容字段。

验收标准：

- 前端不需要知道模型名、provider、api key。
- 功能模块不读取用户等级、不判断模型、不选择 key。
- `run_full_workflow(ctx)` 成为主执行入口。

## 阶段四：TTS-centric Resume（收窄版）

目标：**TTS 按 segment 断点续跑**；TTS 失败时**先交付学习卡**，再允许用户重试补语音。

详细说明见 [tts-centric-resume.md](./tts-centric-resume.md)。

### 产品范围（做）

- 同一 Job 目录重跑时，已有 `{segment}.mp3` + 合法 `.mp3.jsonl` 的 segment **跳过 TTS**（`movie_pipeline.tts_resume`）。
- `POST /api/jobs/:id/retry` 在同一 artifact 目录上重入 workflow。
- **TTS 段级失败为 non-fatal**：保留旁白/词卡 payload，继续 **export 学习卡**；**不 render**（`incomplete_tts`）。
- Job 在 TTS 不完整但学习卡已写出时：`status=failed`，`error_code=tts_partial_failure`，`retryable=true`，`artifacts.studyCardsHtmlPath` 可用。

### 非目标（不做）

- 每 macro stage 的 `POST /resume?from=…`。
- `narration.json` 整阶段跳过视觉理解（重试仍会重跑 narration API，除非日后单独立项）。
- render 成片文件级 resume。

### 已实现 / 待加强

| 项 | 状态 |
|----|------|
| `tts_segment_is_reusable` + pipeline 段级 skip | 已落地 |
| TTS 失败 → 仍 export 学习卡 + `failed` + retry | 已落地 |
| `resume_policy` 外层字幕/帧池复用（重试加速） | 已落地 |
| `test_tts_resume` / `test_tts_partial_study_cards` | 已落地 |
| narration 级 checkpoint | **非目标** |

### 验收标准

- TTS 中途失败后重试：只补缺失 segment 的 mp3，日志有 `segment.tts` skipped/done。
- TTS 失败时用户仍能在 `artifacts/manifest.json` 下载 **学习卡**；成片不出现。
- `workflow.stage.*` 可区分 `tts` 的 `warning_count` / `render` 的 `incomplete_tts` skip。

## 阶段五：超时、重试与失败降级

目标：外部 API 不稳定时，系统可控失败，不长时间假死。

建议配置：

```yaml
capability_timeouts:
  narration: 120
  polish: 60
  study_enrichment: 45
  tts: 90

capability_retries:
  narration: 1
  polish: 1
  study_enrichment: 0
  tts: 2
```

失败级别：

```text
fatal:
  subtitle_extraction
  subtitle_analysis
  narration
  tts, when speech is requested
  render, when video output is requested

non_fatal:
  polish fallback to original narration
  study_enrichment
  study_cards_html
  optional subtitle merge enhancement
```

任务清单：

- 为 gateway chat/speech/embedding 增加 capability timeout。
- 为不同 capability 配置不同 retry 次数。
- 将 study enrichment 改为 non-fatal，失败后记录 warning 并继续。
- 将 polish 失败策略明确为 fatal 或 fallback，避免隐式行为。
- 错误对象标准化：`stage`、`segment_index`、`capability`、`retryable`、`message`。

验收标准：

- API 卡住不会无限等待。
- 学习卡失败不会导致整部视频失败。
- Job 失败时错误信息能直接展示给前端。

## 阶段六：并发与资源调度产品化

目标：并发策略不只写死在 local.yaml，而能结合用户等级和系统负载。

当前保留配置：

```yaml
workflow_parallelism:
  segment_group_size: 3
  segment_group_concurrency: 2

capability_concurrency:
  narration: 2
  polish: 2
  study_enrichment: 1
  tts: 2
  subtitle_context: 4
```

产品化方向：

- 免费用户使用低并发、低成本模型。
- 付费用户使用更高并发或更高质量模型。
- 系统繁忙时降低低优先级 Job 的并发。
- 同一 provider/model 设置全局并发上限，避免 NewAPI 后端排队或 500。
- segment 继续采用 group 并行，group 内顺序执行，保持稳定性。

任务清单：

- 增加 `PolicyContext` 中的并发上限。
- 将 local.yaml 并发配置作为默认值，resolver 根据用户策略生成最终并发。
- 增加 provider/model 级别 limiter。
- 增加 Job 队列，避免所有 Job 同时进入模型调用。

验收标准：

- 多个 Job 同时运行时，不会把同一个模型打爆。
- 用户等级可以影响并发和模型选择。
- 日志可显示请求等待 limiter 的时间。

## 阶段七：API 服务化

目标：前端通过 API 创建、查询、取消任务。

最小 API：

```text
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/artifacts
GET /jobs/{job_id}/logs
POST /jobs/{job_id}/cancel
```

可选增强：

```text
GET /jobs/{job_id}/events
GET /jobs/{job_id}/progress
POST /jobs/{job_id}/resume
```

任务清单：

- 引入轻量 API 层。
- 实现 Job 创建和后台执行。
- 实现 Job 状态查询。
- 实现日志读取。
- 实现 artifact 下载或访问 URL。
- 实现 cancel flag，stage/segment 周期性检查。

验收标准：

- 前端可以提交视频处理任务。
- 前端可以看到当前阶段和进度。
- 用户可以取消长视频任务。
- 成功后可以获取视频、字幕、学习卡等产物。

## 阶段八：启动自检与运维能力

目标：配置错误在启动时暴露，不在长视频跑一半时暴露。

启动自检项：

- `ffmpeg` 可执行。
- output root 可写。
- NewAPI base URL 可访问。
- DashScope TTS 可访问。
- `model_defaults` 都存在于 `model_catalog`。
- provider api key 已配置且非空。
- 关键目录权限正常。

任务清单：

- 实现 `movieteller doctor` 或 `GET /healthz/deep`。
- 将配置错误分级：fatal、warning。
- 对每个 provider 做轻量 smoke test。
- 输出机器可读 JSON 诊断结果。

验收标准：

- 服务启动前能发现缺 key、模型名错误、ffmpeg 不存在等问题。
- 部署环境问题不需要跑完整 workflow 才暴露。

## 阶段九：安全、额度与隔离

目标：让系统可以面对真实用户输入。

任务清单：

- 限制上传文件大小。
- 限制视频时长。
- 限制文件格式。
- 防止路径穿越。
- 每用户限制并发 Job 数。
- 每用户限制每日/每月额度。
- API key 不进入日志。
- 日志中脱敏 base URL 和敏感路径。
- 清理过期 artifact。

验收标准：

- 恶意路径、超大文件、超长视频不会拖垮服务。
- 用户之间的 Job 和产物隔离。
- 日志中没有明文密钥。

## 阶段十：前端体验

目标：把底层 pipeline 状态转成用户能理解的产品状态。

前端展示：

- 上传状态。
- 当前阶段。
- 总进度。
- 当前处理 segment。
- 最近一次模型调用。
- 已生成产物。
- 可恢复/可重试提示。
- 错误说明。

状态映射示例：

```text
subtitle_extraction -> 正在识别字幕
frame_pool -> 正在分析画面
narration -> 正在生成解说
tts -> 正在合成旁白
render -> 正在合成视频
export -> 正在整理结果
```

任务清单：

- 定义前端进度 DTO。
- 从 Job 状态和日志聚合进度。
- 支持查看详细日志。
- 支持下载每类 artifact。
- 支持失败后重试或从 checkpoint 继续。

验收标准：

- 用户不需要看终端就能知道任务进度。
- 失败信息能转成可理解提示。
- 成功后产物入口清晰。

## 推荐实施顺序

```text
1. 日志收口
2. Job 模型和目录标准化
3. WorkflowRequest + ResolvedRunContext
4. Checkpoint/Resume
5. Timeout/Retry/Failure Policy
6. 并发和资源调度
7. API 服务化
8. 启动自检
9. 安全额度隔离
10. 前端体验完善
```

最小可产品化闭环：

```text
POST /jobs
  -> 创建 Job
  -> 生成独立 output_root
  -> 初始化日志
  -> 执行 workflow
  -> 写 Job 状态
  -> 输出 artifacts
GET /jobs/{job_id}
  -> 返回阶段、进度、错误、产物
GET /jobs/{job_id}/logs
  -> 返回 JSONL 日志
```

## 质量门禁、Smoke 测试与 CI

产品化不仅要「能跑通一次」，还要能**反复证明**主链路仍可用。仓库内用 HTTP 冒烟脚本 `scripts/jobs-api-smoke.mjs`（逻辑在 `scripts/jobs-api-smoke-lib.mjs`）分层验证；详见 [jobs-api.md](./jobs-api.md) 与 [jobs-api-smoke.md](./jobs-api-smoke.md)。

### 当前已具备的 Smoke 分层

在 `server/` 目录、**需先** `npm run dev`：

| npm 脚本 | 模式 | 验证范围 | 是否依赖 Python/API |
|----------|------|----------|---------------------|
| `npm run smoke` | `api` | 健康检查、Job 列表、404、上传校验 | 仅 deep health 要求 runner 可 import |
| `npm run smoke:create` | `create` | 创建 Job + 列表/详情/logs 游标 | 创建后不跑完 workflow |
| `npm run smoke:cancel` | `cancel` | 创建 → `POST cancel` → 终态 `canceled` | 需 runner 能启动 |
| `npm run smoke:workflow` | `workflow` | 创建 → 轮询终态 → 成功时查 artifacts | 全栈 + 模型 API |
| `npm run smoke:unit` | — | 脚本参数/终态逻辑单测 | 否 |

环境变量：`MOVIE_TELLER_BASE_URL`、`MOVIE_TELLER_SMOKE_MODE`、`MOVIE_TELLER_SMOKE_VIDEO`、`MOVIE_TELLER_SMOKE_TIMEOUT_SEC`、`MOVIE_TELLER_SMOKE_STRICT=1`。

### `--strict` 是什么

`--mode=workflow` 时：

- **默认（非 strict）**：Job 终态为 `failed` 时脚本仍 **exit 0**，并提示检查 API Key / Python 环境——适合本机尚未配齐密钥、不想误报红。
- **`--strict`**（或 `MOVIE_TELLER_SMOKE_STRICT=1`）：终态必须为 **`succeeded`**，否则脚本 **非 0 退出**，适合当作**合并门禁**。

示例（使用本机已跑通样例的源片，路径见 [jobs-api-smoke.md §4.1](./jobs-api-smoke.md#41-本地已验证的端到端样例2026-05-28)）：

```bash
node scripts/jobs-api-smoke.mjs --mode=workflow --strict \
  --video=artifacts/jobs/<job-id>/input/source.mp4 \
  --timeout-sec=600
```

与稳定性专题文档的对应关系：

| 能力 | 专题文档 |
|------|----------|
| Runner 退出 + `cancel.flag` → `canceled` | [runner-exit-cancel-fix.md](./runner-exit-cancel-fix.md) |
| Gateway retryable 重试 | [gateway-retryable-retry.md](./gateway-retryable-retry.md) |
| `cancel_signal` + Gateway 入口检查 | [cancel-signal-gateway-check.md](./cancel-signal-gateway-check.md) |
| TTS/embedding `capability_timeouts` / `capability_retries` | [capability-timeout-retries.md](./capability-timeout-retries.md) |

### 「CI / smoke --strict 常态化」指什么

**常态化** = 不依赖开发者本机手动跑，而在 **持续集成**（如 GitHub Actions）里按固定节奏自动执行，失败则阻断合并。

典型流水线步骤：

1. 安装 Node 依赖、配置仓库根 `.venv` 并按 [local-development.md §1](./local-development.md#1-python-环境仓库根-venv) editable 安装各 Python 包。
2. 从 CI Secrets 注入 API Key（勿写入仓库）；准备 `config/local.yaml` 或环境变量。
3. 后台启动 `server`（或指向固定测试环境）。
4. 由轻到重：`npm run smoke:unit` → `npm run smoke` →（可选）`npm run smoke:cancel`。
5. **门禁级**：`node ../scripts/jobs-api-smoke.mjs --mode=workflow --strict --video=...`（固定短视频或受控 fixture）。
6. 任一步失败 → PR 检查失败。

这与「本机曾 succeeded 一次」的区别：

| 状态 | 含义 | 端到端置信度（主观） |
|------|------|----------------------|
| 本机单次 succeeded Job | 证明环境+密钥+代码路径可成片 | 约 **74**（参见 `artifacts/jobs/` 下样例记录） |
| 每次 PR 自动 `smoke --strict` 通过 | 回归防护，防静默退化 | 目标 **85+** |
| 仅 `smoke` / `smoke:create` 在 CI | 只锁 HTTP 契约，不锁成片 | API 层约 **88**，成片仍低 |

`artifacts/` 已在 `.gitignore`：样例 Job 目录作**本机对照**，不进 git；CI 需自备短视频（或后续允许的 fixture 路径）与 Secrets。

### 产品化阶段的 Smoke 目标（建议）

| 阶段 | Smoke 目标 |
|------|------------|
| **当前（MVP 已通）** | 文档化 + `smoke` / `create` / `cancel` / `unit`；本机 workflow 可 succeeded |
| **下一档** | 团队约定：发版前本地跑 `smoke:workflow --strict`；修齐 `.venv` 使 `healthz/deep` 稳定为 ok |
| **CI 常态化** | Actions（等）中 `smoke:unit` + `smoke` 每 PR；`workflow --strict` 每日或 main 分支（控成本与密钥） |
| **成熟** | 固定 30～60s 测试片 + 密钥轮换；失败自动附 `job.error` / `workflow.jsonl` 片段 |

实现 CI 时可选新增 `.github/workflows/smoke.yml`（尚未纳入仓库时，以本节为规格说明）。

可观测性合同测已纳入 [`.github/workflows/python-observability.yml`](../.github/workflows/python-observability.yml)（与 smoke 独立，不消耗 API Key）。

### 阶段七 / 八 与 Smoke 的验收补充

在 [阶段七](#阶段七api-服务化) 验收基础上，建议增加：

- `npm run smoke` 在配置齐全环境下通过（含 `GET /api/healthz/deep`）。
- 至少一次 `smoke:workflow` 对本机真实短视频 `succeeded`（或 CI strict 通过）。
- `POST /jobs/:id/retry`、取消与终态语义与 [runner-exit-cancel-fix.md](./runner-exit-cancel-fix.md) 一致。

## 非目标

短期不做：

- 多 provider 自动竞价。
- 复杂 key 池调度。
- 分布式 worker。
- 多租户计费系统。
- 完整 APM/Tracing 平台。
- 过度可配置的 stage 插件系统。

这些能力可以在 Job 化、日志、resume、API 稳定后再考虑。
