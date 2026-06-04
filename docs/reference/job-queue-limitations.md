# Job 队列限制与 Phase 2 方向

Phase 1 使用 **单 Node 进程内的内存队列**（[`jobQueue.js`](../server/src/services/jobs/jobQueue.js)）。本文档列出已知场景、行为与风险，以及 Phase 2 的缓解方案。

## 场景 × 行为 × 风险

| 场景 | 当前行为 | 风险 | Phase 2 方案 |
|------|----------|------|----------------|
| 单进程 `npm run dev`（combined） | 上传 → 内存队列 → spawn Python | 进程崩溃丢失内存队列；磁盘 `queued` 在重启时被标 `failed` | 可选 worker 分进程 + 文件 `queued` 由 worker 拾取 |
| 多 Node 实例（未配置 RUN_MODE） | 每实例独立内存队列，可能双 spawn | 重复执行、状态竞争 | Postgres `SKIP LOCKED` 或 BullMQ + claim |
| `RUN_MODE=api` + `worker` 分进程 | API 只写 `queued`；worker 轮询拾取 | 误同时跑 combined + worker | 运维约束 + `worker.lock` |
| `RUN_MODE=api` 单独跑 | 不 recovery、不 spawn | 磁盘 `queued` 永不执行 | 必须配 worker |
| API 进程跑旧版 recovery | 将磁盘 `queued` 标 `failed` | Job 永久失败 | API 禁止 `recoverJobsOnStartup`（已实现分角色 recovery） |
| 取消 queued Job | Node 直接 `canceled` | — | 同左；worker 跳过 `cancel.flag` |
| 取消 running Job | `cancel.flag` + Python 检查点 | 长阶段可能延迟 | 心跳 + stale claim |
| 列表 API `limit` | 最大 **1000** / 用户 | 超大历史单次 payload | DB 分页 + 索引 |
| 3 天 retention | 删除整 Job 目录 | 无软删除 | `deleted_at` + 异步清理 |
| NFS / 多机共享 `JOBS_ROOT` | `worker.lock` 不可靠 | 双 claim | 队列在 DB，产物在对象存储 |

## RUN_MODE 摘要

| 模式 | recovery | enqueue spawn | retention 调度 |
|------|----------|---------------|----------------|
| `combined`（默认） | 全部 `queued`/`running` → `failed` | 内存队列 + spawn | 默认开启 |
| `api` | 无 | 仅写 `queued` | 可选 `RUN_SCHEDULER=0` |
| `worker` | 仅孤儿 `running` | `queueWorker` 拾取 | 关闭 |

详见 [`worker-runtime.md`](worker-runtime.md) 与 [`job-lifecycle.md`](job-lifecycle.md)。
