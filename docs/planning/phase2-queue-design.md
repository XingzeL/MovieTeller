# Phase 2 队列设计（设计-only）

> 本文档不实施代码；供 Postgres / BullMQ 选型与运维模型对齐。
>
> 当前小并发实施方案见 [phase2-lite.md](../reference/phase2-lite.md)。本文保留为完整分布式 Phase 2 参考。

## 目标

- 多 API 实例安全入队与 claim
- 取消、心跳、stale job 回收
- 与现有 filesystem Job 目录兼容（短期双写）

## 推荐方向

**优先：Postgres + `FOR UPDATE SKIP LOCKED`**

| 能力 | 方案 |
|------|------|
| 入队 | `INSERT jobs (status='queued', user_id, ...)` |
| claim | `UPDATE ... WHERE status='queued' ... SKIP LOCKED RETURNING *` |
| 心跳 | `last_heartbeat_at` 周期更新；超时 → `failed` 或 requeue |
| stale | 定时任务扫描 `running` 且 heartbeat 过期 |
| cancel | `cancel_requested_at` + worker 检查；或 status 直接 `canceled` |
| leader lock | 单 scheduler 实例（`pg_advisory_lock` 或 lease 行） |

**备选：BullMQ + Redis**

- 成熟重试/延迟；需 Redis 运维
- Job 元数据仍在 Postgres 或仅 Redis（需评估持久化）

## 与 Phase 1 边界

| Phase 1 | Phase 2 |
|---------|---------|
| 内存 `waiting[]` | DB 队列 |
| `worker.lock` 文件 | 行级 claim |
| `recoverJobsOnStartup` 标 failed | heartbeat + stale 策略可配置 |
| `artifacts/jobs/{id}/` | 可选对象存储 + manifest URL |

## 部署拓扑（目标）

```text
[Browser] → [API x N] → Postgres (jobs)
                ↓
         [Worker x M] → spawn Python → JOBS_ROOT or object store
                ↓
         [Scheduler x 1] → retention + stale sweep
```

## 迁移步骤（草案）

1. 新 Job 双写：`workflow.json` + `jobs` 行
2. Worker 从 DB claim，仍读写同一 `job_id` 目录
3. 列表/详情 API 读 DB；文件为 runner 真相源
4. 关闭内存 `jobQueue.waiting`

## Open decisions

- Clerk `sub` 作为 `user_id` 或内部 UUID 映射表
- 是否保留 filesystem 为 sole artifact store（推荐短期保留）

参见 [multi-user-data-model.md](../reference/multi-user-data-model.md)、[job-queue-limitations.md](../reference/job-queue-limitations.md)。
