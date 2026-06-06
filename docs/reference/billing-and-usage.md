# Billing and usage (M7)

Postgres-backed quota, reservation, clipping, and usage ledger. Applies when `DATABASE_URL` is configured.

## Plans (seed data)

| code | Monthly quota | Max single video | Daily cap |
|------|---------------|------------------|-----------|
| `free` | 5 min | 3 min | none |
| `lite` | 120 min | 15 min | 60 min |
| `pro` | 300 min | 30 min | 120 min |
| `max` | 450 min | 50 min | 150 min |

## Create job flow

1. Upload to temp path; `ffprobe` → `source_duration_sec` (30s timeout).
2. Transaction: `upsertUser` → `ensureActiveBillingPeriod` → `resolveProcessingRange` → reserve `FOR UPDATE` → `INSERT jobs` (queued).
3. After commit: write disk (`request.json` with `startPoint`/`endPoint`, `workflow.json`).
4. Disk failure: `releaseQuota` + `DELETE jobs` + remove directory.

### Errors

| HTTP | `code` | When |
|------|--------|------|
| 400 | `video_probe_failed` | ffprobe missing/timeout/invalid duration |
| 400 | `plan_quota_exhausted` | Cannot reserve minutes for planned processing |
| 503 | `database unavailable` | Postgres unreachable |

## Clipping

- Node computes `endPoint = min(source, plan max, monthly remaining, daily remaining)`.
- `quota_clip_applied` when `endPoint < source_duration_sec`.
- Python `job_runner` trims to `input/processed.mp4` before `run_full_workflow`; clears `start_point`/`end_point` on the workflow request.

## Reservation and finalize

- `reserved_minutes` on `jobs` and `user_balances` / `user_daily_usage` at create.
- Terminal reconcile: `finalizeBilling` with `WHERE billing_finalized_at IS NULL`.
- **Succeeded**: release reserved, deduct `remaining`, add daily consumed, insert `usage_ledger`.
- **Failed/canceled**: release reserved only; ledger `consumed_minutes = 0`.

## API

### `GET /api/usage`

- `records`: `usage_ledger` last 3 days.
- `summary`: `remainingMinutes` (`remaining - reserved`), `consumedInPeriod`, period boundaries.

Requires auth; returns 503 without DB.

## Retention

- Jobs: disk first, then `DELETE jobs` (3 days, terminal only).
- `usage_ledger`: independent `DELETE` by `created_at` (3 days).
- `job_study_cards`: `ON DELETE CASCADE` from `jobs`.

## Study cards

- Python still writes HTML to disk; worker upserts `job_study_cards` on success.
- `resolveStudyCardsArtifact`: DB preferred, disk fallback for list/inline/download.
