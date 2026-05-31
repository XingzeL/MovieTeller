# Multi-User Data Model (Draft)

Phase 1 mapping to filesystem; Phase 2+ may add Postgres.

## Entities

| Entity | Phase 1 | Phase 2+ |
|--------|---------|----------|
| **User** | Cookie / `req.user.id` string | `users` table + Clerk id |
| **Job** | `{JOBS_ROOT}/{jobId}/` + `workflow.json` | `jobs` row + workflow artifact |
| **Artifact** | Files + `artifacts/manifest.json` | Optional object storage URLs |
| **RetentionPolicy** | Code constants (3 days, download-once) | Per-plan config |
| **Plan / Credits** | Not implemented | Billing tables |

## Relationships

- User 1—N Job (`workflow.user_id`)
- Job 1—N Artifact files
- Audit (Phase 3): `logs/audit.jsonl` per job

## Identity flow

```text
Browser mt_uid → currentUser → createJob writes user_id → jobAccess reads user_id
```

Future: Clerk session replaces `mt_uid`; `jobAccess` unchanged.
