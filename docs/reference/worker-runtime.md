# Worker runtime (RUN_MODE)

Phase 1 默认 **`combined`**：单进程内 HTTP + 内存队列 + spawn + retention（与历史 `npm run dev` 一致）。

可选拆分（本地或预生产）：

| `MOVIE_TELLER_RUN_MODE` | 进程职责 | recovery | spawn |
|-------------------------|----------|----------|-------|
| `combined`（默认） | 全部 | `queued`/`running` → `failed` | `jobQueue` 内存队列 |
| `api` | 仅 HTTP | **不执行** | **禁止**；`POST /api/jobs` 只写磁盘 `queued` |
| `worker` | 轮询拾取 | 仅孤儿 `running`（无 live `runner.pid`） | `queueWorker` + `worker.lock` |

## 环境变量

- `MOVIE_TELLER_RUN_MODE` 或 `RUN_MODE`：`combined` | `api` | `worker`
- `RUN_SCHEDULER=0`：关闭 retention 调度（通常 worker 进程关闭；API 可选）

## npm scripts

```bash
cd server
npm run dev              # combined
npm run dev:api          # api only
npm run dev:worker       # worker loop only
```

**运维约束**：不得同时以 `combined` 与 `worker` 处理同一 `JOBS_ROOT`，否则会双 spawn。

## Recovery 矩阵

| 磁盘 status | combined | api | worker |
|-------------|----------|-----|--------|
| `queued` | → `failed` (server_restarted) | 不变 | 不变（待拾取） |
| `running` | → `failed` | 不变 | 若 runner 已死 → `failed` (orphan) |

## 文件

- `logs/runner.pid` — spawn 后写入子进程 pid（worker 判断存活）
- `worker.lock` — worker 拾取前 O_EXCL 锁（[`claimJob.js`](../server/src/services/jobs/claimJob.js)）

## Cancel 与磁盘

- `queued` + `cancel.flag`：worker **不拾取**
- API 模式 `cancelJob`：与 combined 相同语义，但不 spawn

详见 [job-lifecycle.md](job-lifecycle.md)、[job-queue-limitations.md](job-queue-limitations.md)。
