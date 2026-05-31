# Worker Runtime Strategy (Design)

## Current (single process)

```text
API (Express)
  → enqueueJobUpload / jobQueue (memory)
  → spawnPreparedJob → Python job_runner
  → recoverJobsOnStartup + retention scheduler (bootstrap)
```

## Target roles

| Role | Responsibility |
|------|----------------|
| **API** | HTTP, auth, jobAccess, uploads |
| **Worker** | Claim queued jobs, run Python |
| **Scheduler** | Retention, recovery |

Phase 1 implements **bootstrap** split (`createApp` vs `startApiRuntime`) but still runs all roles in one process unless `RUN_SCHEDULER=0`.

## Claiming (future)

- Do **not** rely on `worker.lock` on NFS for production multi-machine.
- Prefer Postgres `FOR UPDATE SKIP LOCKED` or BullMQ.
- Optional single-machine `worker.lock` only after a single `claimAndSpawn(jobId)` entry point exists.

## `recoverJobsOnStartup` vs worker

Today recovery marks stale jobs **failed**, does not re-queue. A future worker loop should define whether to re-queue or leave failed.
