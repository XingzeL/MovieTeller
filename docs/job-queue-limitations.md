# Job Queue Limitations

The Node server uses an **in-memory queue** (`server/src/services/jobs/jobQueue.js`):

- `running` Set and `waiting` array live in process memory.
- **Single process only** — multiple API instances each have their own queue and may duplicate work.
- Server restart: in-memory queue is lost; `recoverJobsOnStartup` marks orphaned `queued`/`running` workflows as `failed`.

## Multi-user note

Queue entries carry `userId` for spawned jobs, but **authorization** is enforced via `workflow.json` + `jobAccess`, not the queue.

## Migration paths

1. Short term: single API + single worker process.
2. Mid term: Postgres `jobs` table with `FOR UPDATE SKIP LOCKED`.
3. Alternative: Redis / BullMQ for Node-native workers.

See [multi-user-readiness-work-items.md](./multi-user-readiness-work-items.md) worker strategy section.
