# Phase 2 Lite：Postgres 控制面与单 Worker

本文档是当前 Phase 2 的实施合同。它面向小并发场景（约 3 人同时使用）：用 Postgres 接管 Job 控制面，但继续保留本地 `artifacts/jobs/`、Python `job_runner` 与 API 代理下载。

完整分布式方案见 [phase2-queue-design.md](../planning/phase2-queue-design.md)。本期不是 Full Phase 2。

## 目标

| 约束 | 设计取向 |
|------|----------|
| 小并发、长任务 | 单 API、单 Worker，Worker 一次只跑 1 个 Job |
| 高单任务成本 | 稳定性优先，不自动 retry |
| 用户隔离、下载一次、审计 | Postgres `jobs` 为用户态真相源 |
| 产物仍本地 | 不迁 S3/MinIO，不做 presigned URL |

一句话：把 Job 控制面从“内存队列 + 扫 `workflow.json`”迁到 Postgres；不改 Python 主流程和产物目录。

## 锁定决策

| 决策 | 合同 |
|------|------|
| Worker 并发 | 每个 Worker 进程一次只跑 1 个 Job |
| Retry | 无自动 retry/requeue；只允许用户或显式 API 手动 retry |
| Stale | heartbeat 超时写 `failed + retryable + error_code=stale_heartbeat` |
| renderedVideo | 禁止 presigned 直出；继续 API 代理流式下载 |
| 视频大小 | 当前成片按 200MB 上限设计；提高上限需重新评估代理下载成本 |
| DB 真相源 | Dashboard、ACL、retryable、下载一次状态以 Postgres 为准 |
| 产物存储 | 本期仍为本地 `artifacts/jobs/` |
| 生产拓扑 | `api + worker`；`combined` 仅本地 dev |
| DB 不可用 | fail fast，不 fallback 到扫盘或内存队列 |

## 目标架构

```text
Browser
  -> Express API (RUN_MODE=api)
  -> Postgres jobs
  -> Single Worker (RUN_MODE=worker)
  -> artifacts/jobs/{jobId}/
  -> python job_runner
```

生产建议：

| 角色 | 数量 | 说明 |
|------|------|------|
| API | 1 | `MOVIE_TELLER_RUN_MODE=api` |
| Worker | 1 | `MOVIE_TELLER_RUN_MODE=worker` |
| Postgres | 1 | Job 状态源 |
| 磁盘 | 1 | `JOBS_ROOT`，需要定期备份 |

## 与 Phase 1 的差异

| 能力 | Phase 1 | Phase 2 Lite |
|------|---------|--------------|
| Job 状态源 | `workflow.json` + 扫目录 | Postgres `jobs` |
| 队列 | 进程内 `waiting[]` | DB `status='queued'` |
| 执行 | combined 或 worker 扫盘 spawn | 单 Worker 从 DB claim 后 spawn |
| API 重启 | queued/running 依赖 recovery | queued 留在 DB |
| 列表/详情 | 扫 `artifacts/jobs/` | SQL `WHERE user_id=$current` |
| 用户隔离 | `workflow.json.user_id` | `jobs.user_id` |
| 取消 | `cancel.flag` 为主 | DB `canceling` + `cancel.flag` |
| 重试 | 文件态 requeue | DB queued，手动触发 |
| 下载一次 | `workflow.json` 字段 | DB 字段，API 代理下载 |

## 数据表

建议 `jobs` 表字段：

| 列 | 说明 |
|----|------|
| `job_id` UUID PK | 与 `artifacts/jobs/{jobId}/` 一致 |
| `user_id` TEXT NOT NULL | Clerk user id |
| `status` | `queued` / `running` / `canceling` / `succeeded` / `failed` / `canceled` |
| `attempt_id` INT NOT NULL DEFAULT 1 | 防旧 worker 写回覆盖新 retry |
| `created_at`, `updated_at` | 列表排序 |
| `started_at`, `completed_at` | 执行耗时与排障 |
| `output_root` TEXT | 本地 Job 目录绝对路径 |
| `claimed_at`, `claimed_by` | Worker claim 信息 |
| `last_heartbeat_at` | running/canceling 期间刷新 |
| `cancel_requested_at` | 用户请求取消 |
| `cancel_acknowledged_at` | Worker 已写 `cancel.flag` |
| `cancel_deadline_at` | 协作取消超时点 |
| `canceled_at`, `cancel_mode` | `cooperative` / `forced` |
| `error_code`, `error_message`, `retryable` | 失败与重试 |
| `original_source` JSONB | 展示元数据 |
| `video_downloaded_at`, `video_purged_at`, `video_state_version` | 视频下载一次策略 |

索引：

```sql
CREATE INDEX jobs_user_updated_idx ON jobs (user_id, updated_at DESC);
CREATE INDEX jobs_claim_idx ON jobs (status, created_at);
```

## 执行流程

创建 Job：

```text
POST /api/jobs
  -> 写 artifacts/jobs/{jobId}/input、request.json、workflow.json
  -> INSERT jobs(status='queued', user_id=...)
  -> API 不 spawn Python
```

Worker：

```text
loop
  -> claim 一条 queued
  -> UPDATE status=running, claimed_by, last_heartbeat_at
  -> spawn python job_runner
  -> heartbeat
  -> 子进程退出后读 workflow.json
  -> UPDATE jobs 终态
```

Worker 所有写回必须带：

```sql
WHERE job_id = $1
  AND attempt_id = $2
  AND claimed_by = $3
```

Claim 事务必须短小，只做 DB claim；不要在事务里下载文件、spawn Python 或读写大文件。

## 取消

状态机：

```text
queued  -> canceled
running -> canceling -> canceled
```

Running cancel：

```text
API 写 status=canceling, cancel_requested_at, cancel_deadline_at
Worker 看到 canceling
  -> 写 cancel.flag
  -> 写 cancel_acknowledged_at
Python checkpoint 读 cancel.flag
  -> 协作退出，workflow.json 写 canceled
Worker reconcile
  -> DB 写 canceled, canceled_at, cancel_mode=cooperative
```

若到 `cancel_deadline_at` 仍未退出：

```text
SIGTERM process group
等待 30s
SIGKILL process group
DB 写 canceled, cancel_mode=forced
```

实现要求：

- spawn Python 时避免 `shell: true`。
- POSIX 下 `detached: true`，对进程组发信号（`kill(-pid)`），减少 ffmpeg / VideoCaptioner 子进程残留。
- 用户主动取消最终显示 `canceled`，不显示 `failed`。
- **顺序**：`isForcedCancelEligible`（仅校验）→ 杀进程组 → outcome 为 `killed` / `already_exited` / `no_pid` 时 `markJobForcedCanceledByWorker` → 写 `workflow.json`；kill 失败则保持 `canceling` 并写 `error_code=forced_cancel_kill_failed`。stale `attempt_id` / `claimed_by` 全程不会误伤磁盘或误杀。

| 环境变量 | 说明 |
|----------|------|
| `CANCEL_DEADLINE_MINUTES` | 生产默认（如 30） |
| `CANCEL_DEADLINE_SECONDS` | 测试用秒级 deadline |
| `FORCED_CANCEL_KILL_GRACE_MS` | SIGTERM 后等待（默认 30000） |
| `FORCED_CANCEL_POST_KILL_POLL_MS` | SIGKILL 后回收轮询（默认 1000） |
| `MOVIE_TELLER_FAKE_HANGING_RUNNER` | `1` + test/allow 时装假 runner |

| 阶段 | 内容 |
|------|------|
| M4a | DB `canceling` + `cancel.flag` + 手动 retry |
| M4b | deadline + 进程组信号 + `cancel_mode=forced`（已实现，POSIX） |

## Retry

无自动 retry。仅用户或显式 API 触发：

- `canceled`：一律可手动 retry。
- `failed`：仅当 `retryable = true` 时可 retry（如 `stale_heartbeat`）；不可重试的失败需用户重新上传新 Job。

```text
failed/canceled -> queued
attempt_id += 1
clear claimed_*, last_heartbeat_at, cancel_*, error_*
```

retry 前必须确认 `input/source.mp4` 仍存在；如果输入已被 retention 清理，返回不可 retry。

## Heartbeat 与 Stale

Worker 每约 30 秒刷新 `last_heartbeat_at`。

单实例 stale sweep：

```text
status IN ('running', 'canceling')
AND last_heartbeat_at < now() - 90s
  -> failed
  -> error_code=stale_heartbeat
  -> retryable=true
```

本期不做 leader election；部署保证只有一个 sweep 进程。

## renderedVideo 下载一次

`renderedVideo` 必须走 API proxy，不允许 presigned 直出：

```text
GET /api/jobs/:id/artifacts/renderedVideo
  -> DB ACL 校验 user_id
  -> DB 判断 video_downloaded_at / video_purged_at
  -> 已下载返回 410
  -> API 从本地文件流式代理
  -> 响应成功结束后：
       UPDATE video_downloaded_at, video_state_version
       append audit job.video_downloaded
       删除本地 renderedVideo
       UPDATE video_purged_at
```

`studyCardsHtml` 不受视频清理影响，仍可 inline/下载。

## 历史 Job 策略

Phase 2 Lite 只保证新 Job 写入 Postgres。

| 类型 | 策略 |
|------|------|
| 新 Job | 写 DB + 文件双写 |
| 有 `user_id` 的旧格式 Job | 可选 backfill 脚本迁移 |
| 无 `user_id` 的旧 Job | 不迁移、不可见 |
| 无 DB row 的 Job | 默认不出现在 Dashboard |

backfill 是可选工具，不是 Phase 2 Lite 主链路。脚本：[`server/scripts/jobs-backfill.mjs`](../server/scripts/jobs-backfill.mjs)（`npm run db:backfill`，支持 `--dry-run`）。

## 本地开发入口

Phase 2 Lite 验证路径：

```bash
# 1. 启动 Postgres
docker compose up postgres

# 2. 跑 migration
cd server
npm run db:migrate

# 3. 启动 API
npm run dev:api

# 4. 另开终端，启动 Worker
npm run dev:worker

# 5. 另开终端，启动前端
cd client
npm run dev
```

`npm run dev` / `combined` 可保留给本地快速调试，但 Phase 2 Lite 的验收必须使用 Postgres + `dev:api` + `dev:worker`。

## 里程碑

| 里程碑 | 内容 |
|--------|------|
| M0 | 本文档 + `job-lifecycle.md` 附录 |
| M1 | Postgres、migration、Compose、本地 dev 文档 |
| M2 | API enqueue + 单 Worker claim/spawn/reconcile |
| M3 | list/read/jobAccess/Dashboard DTO 改读 DB |
| M4a | `canceling` + `cancel.flag` + 手动 retry |
| M4b | cancel deadline + 进程组信号兜底 |
| M5 | heartbeat + stale sweep |
| M6 | 下线内存 `waiting[]` 主路径、smoke/CI/runbook |

## 验收标准

1. 创建 Job 后 Postgres 有 `queued` 行，本地目录与 Phase 1 一致。
2. 单 Worker claim 后 DB 为 `running`，`last_heartbeat_at` 持续更新。
3. Python 结束后 DB 为正确终态，manifest 产物可下载。
4. Dashboard 只显示当前 `user_id` 的 Job。
5. 取消 running：DB/UI 见 `canceling`，最终 `canceled`。
6. Worker 被 kill：超时后 DB `failed + retryable`，不永久 `running`。
7. 用户手动 retry：`failed/canceled -> queued`，Worker 再次 claim。
8. 视频下载一次：DB 记录，重复请求 410，学习卡仍可访问。
9. API/Worker 重启后 queued 不丢。
10. `npm run smoke` / `smoke:create` 在 Postgres + api + worker 下通过。
11. retry 后 `attempt_id` 递增，旧 attempt reconcile 不能覆盖新 attempt。
12. DB down 时 protected Job API fail fast，返回 503，不 fallback 扫盘。
13. forced cancel 用户态仍显示 `canceled`，audit/detail 标明 `cancel_mode=forced`。

### 当前验收记录

**Phase 2 Lite 验收状态：通过**（生产拓扑 `api` + `worker` + Postgres；M6 代码侧 `waiting[]` 清理与公网 runbook 不阻塞部署）。

#### 2026-06-02（自动化 / smoke）

- `cd server && npm test`：通过（53 pass / 1 skip）。
- `DATABASE_URL=postgresql://movieteller:movieteller@127.0.0.1:5432/movieteller npm run test:db`：通过（15 pass）。
- `MOVIE_TELLER_BASE_URL=http://localhost:3101 npm run smoke:create`：Postgres + `start:api` + `start:worker` 下通过。

#### 2026-06-04（人工 / 生产拓扑）

- `MOVIE_TELLER_BASE_URL=http://localhost:3001 npm run smoke:cancel`：通过；示例 Job `524c0a2b-af7d-4cd2-a4af-c030a7a4d002` 终态 `canceled`（`start:api` + `start:worker` + Postgres）。
- **DB down → 503（验收 #12）**：`docker compose stop postgres` 后 `curl -H "Cookie: mt_uid=smoke-user" http://localhost:3001/api/jobs` → `HTTP/1.1 503`，body `{"error":"database unavailable"}`；未 fallback 扫盘。`docker compose start postgres` 后 API 恢复；Worker 在 DB 断开期间可能退出，已用 `npm run start:worker` 重启并见 `[runtime] worker loop started`。
- **前端真实 workflow**：浏览器上传 → Job 跑通 → 终态 `succeeded`（完整 Python/API 环境，非 `smoke:workflow --strict` 脚本）。

#### 可选 / 非 Lite 阻塞

- `smoke:workflow --strict`：发版前可用固定短视频 + API key 再跑一轮 CLI 回归；前端 succeeded 已覆盖端到端成片路径。
- M6 工程收尾：`combined` 路径下 `waiting[]` 代码删除、单机公网 runbook 文档化（见里程碑 M6）。

## 暂缓

| 项 | 触发条件 |
|----|----------|
| S3 / MinIO | 用户规模上升或需要多机 Worker |
| presigned URL | 与对象存储一并评估；renderedVideo 仍 proxy |
| 多 API 实例 | 需要 LB + 仅 api 模式 |
| 多 Worker + 大规模竞争测试 | 单 Worker 饱和后 |
| scheduler leader | 多实例跑 retention/stale |
| 自动 retry | 产品明确需要 |

## 风险

| 风险 | 缓解 |
|------|------|
| DB 与 `workflow.json` 不一致 | Worker 子进程退出后统一 reconcile；用户态以 DB 为准 |
| 旧 attempt 写回覆盖新 retry | `attempt_id + claimed_by` 条件更新 |
| cancel 卡在外部 CLI | `cancel_deadline_at` + 进程组信号兜底 |
| DB 不可用 | fail fast，返回 503；Postgres 需备份与重启策略 |
| 磁盘满 | retention 保持 3 天；备份 `JOBS_ROOT` |
| 单 Worker 成瓶颈 | 当前小并发可接受；未来加 Worker 复用 claim SQL |
| renderedVideo 代理占用 API 带宽 | 当前 200MB 上限可接受；仅视频走 proxy |

## M7 扩展（计费与 retention 对齐）

在 Phase 2 Lite 之上已落地：

- 迁移 `002`–`005`：`jobs` 时长/预占字段、`users`/`plans`/余额、 `usage_ledger`、`job_study_cards`。
- 创建时预占额度；超额裁剪（Node 算范围，Python `quota_clip`）。
- `GET /api/usage`；retention 先删盘再删 `jobs` 行。

合同见 [billing-and-usage.md](billing-and-usage.md)。
