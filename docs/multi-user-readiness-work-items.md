# Multi-User Readiness Work Items

This document tracks the architecture work recommended before MovieTeller
continues into a multi-user system. Confidence scores reflect current code
shape, implementation clarity, and expected risk.

## Summary

The current architecture can continue evolving, but multi-user work should not
be added directly on top of the existing single-user job access paths. The
lowest-risk path is to first introduce a user context, user-aware job access,
and clearer runtime boundaries for API, worker, and scheduler behavior.

## Work Items

| # | Work item | Confidence | Notes |
|---:|---|---:|---|
| 1 | Establish `currentUser` middleware | 95% | Provide one canonical user context, even if it starts as a demo user. Stop trusting `userId` from request bodies. |
| 2 | Create a user-aware Job access layer | 92% | Add APIs such as `readJobForUser`, `listJobsForUser`, `resolveArtifactForUser`, and `cancelJobForUser` to centralize owner checks. |
| 3 | Set Job owner from `currentUser` during creation | 95% | Creation should ignore or remove frontend/body `userId` to prevent spoofing. |
| 4 | Add permission boundaries to all Job APIs | 94% | Cover `/jobs`, `/jobs/:jobId`, artifacts, thumbnail, logs, progress, cancel, and retry. |
| 5 | Add cross-user access tests | 96% | User A must not read, download, cancel, or retry User B's jobs. |
| 6 | Normalize Job DTO availability fields | 88% | Backend should return fields like `canDownloadVideo`, `canOpenStudyCards`, and `videoState` so frontend does not infer policy. |
| 7 | Consolidate storage and retention policy | 90% | Unify "download-once video purge" and "delete old job after retention period" into a retention policy/service. |
| 8 | Split API server startup side effects | 85% | Move recovery, retention scheduler, and future worker startup out of `index.js` into explicit runtime/worker modules. |
| 9 | Evaluate and contain the in-memory queue | 82% | Current `jobQueue` is single-process only. Multi-user MVP can keep it only with an explicit limitation and migration path. |
| 10 | Define a multi-user data model draft | 87% | Clarify User, Job, Artifact, RetentionPolicy, Plan, and Credits relationships, even if phase one still uses the filesystem. |
| 11 | Normalize frontend permission and empty states | 86% | Dashboard, StudyCardPage, and Workspace should handle 403, 404, purged jobs, and non-owned jobs. |
| 12 | Keep test artifacts isolated and self-cleaning | 93% | Tests should delete their own `artifacts/test-*` output and never pollute real job history. |
| 13 | Document the current Job lifecycle contract | 91% | Capture `workflow.json` fields, status transitions, download-once video policy, and study-card retention/cleanup behavior. |
| 14 | Add basic audit logging | 78% | Record create, video download, study-card open/download, cancel, and retry events for future billing and support. |
| 15 | Design the worker strategy before multi-instance deployment | 75% initial; see updated assessment below | Decide whether API, queue, scheduler, and worker run as separate roles to avoid duplicate execution and cleanup. |

## Recommended Order

1. `currentUser` middleware.
2. Job owner from `currentUser`.
3. User-aware Job access layer.
4. Permission checks on every Job API.
5. Cross-user access tests.
6. Job DTO availability fields.
7. Retention policy consolidation.
8. Job lifecycle documentation.

Items 9, 14, and 15 need more design care because they affect deployment shape,
runtime ownership, and future scale.

## Worker Strategy Research

Item 15 originally had a 75% confidence score because the correct worker strategy
depends on deployment constraints: single machine vs. multiple machines, shared
filesystem vs. object storage, and whether Postgres or Redis is available.

After additional research, the recommendation is to split the worker strategy
into staged options.

### Current State

Current behavior is single-instance oriented:

```text
API Server
  -> accepts uploads
  -> creates workflow.json
  -> stores queued/running state in in-memory jobQueue
  -> spawns Python pipeline
  -> runs recovery on startup
  -> runs retention scheduler
```

This works for a single process, but multiple API instances would each have
their own memory queue and could also duplicate recovery or retention work.

### Target Role Split

Recommended short-term target:

```text
API Server
  -> upload, list, read, cancel, retry, download artifacts
  -> does not spawn Python directly

Worker Process
  -> scans queued jobs
  -> claims one job
  -> runs Python pipeline
  -> updates workflow.json

Scheduler Process
  -> retention cleanup
  -> stale job recovery
```

This can still run on one machine at first, but the roles become explicit.

### Strategy Options

| Strategy | Fit | Confidence | Assessment |
|---|---|---:|---|
| Single machine, split API/Worker/Scheduler, filesystem lock | Near-term MVP | 84% | Good first step. Keeps current `workflow.json` model while reducing API responsibilities. |
| Multiple API instances, single Worker, shared filesystem | Small production / internal launch | 86% | Safer than multiple workers. Requires shared storage or colocated processes. |
| Multiple API instances, multiple Workers, shared filesystem lock | Transitional only | 68% | Risky long term. File locking can be fragile on network filesystems. |
| Postgres job table with `FOR UPDATE SKIP LOCKED` | Strong mid-term option | 88% | Good fit once multi-user data, billing, and audit records exist in Postgres. |
| Redis/BullMQ | Strong Node queue option | 86% | Mature worker model with lock renewal, stalled job handling, retries, and concurrency controls. |
| Cloud queue plus object storage | Production cloud option | 82% | Scales well, but requires idempotent execution because delivery is generally at-least-once. |

### Updated Confidence for Item 15

If item 15 is scoped as "design only", with a staged migration plan:

| Scope | Confidence |
|---|---:|
| Design confidence | 88% |
| Short-term role split implementation | 84% |
| True multi-machine production implementation | 82% |

The confidence can rise above 90% only after deciding whether the future stack
will include Postgres, Redis/BullMQ, object storage, or a cloud queue.

## Suggested Worker Evolution

### Phase 1: Keep Single Instance, Clarify Boundaries

```text
API Server = HTTP only
Worker = job execution
Scheduler = retention and recovery
workflow.json = current durable state
artifacts/jobs = current storage
```

### Phase 2: Add Durable Claiming

Use a claim mechanism so only one worker owns a job:

```text
artifacts/jobs/{jobId}/worker.lock
```

Claim should be atomic, for example with exclusive file creation. This is
acceptable for a single machine, but should not be treated as the final
multi-machine design.

### Phase 3: Move Scheduling to Durable Infrastructure

Preferred options:

- Postgres jobs table with row-level claiming.
- Redis/BullMQ if queue behavior is the priority.
- Cloud queue plus object storage if deploying into managed cloud infrastructure.

At this stage, `workflow.json` can remain a pipeline artifact, but it should no
longer be the only source of truth for user-facing job state.

## Open Decisions

- Will the production deployment include Postgres?
- Will Redis be acceptable as an operational dependency?
- Will artifacts remain on local/shared disk, or move to object storage?
- Is the first multi-user release single-machine or multi-machine?
- Are plan/credit limits needed in the first multi-user release?

These decisions should be made before implementing true multi-instance worker
execution.
