# Billing and usage (M7 / dual quota)

Postgres-backed quota, reservation, clipping, and usage records. Applies when `DATABASE_URL` is configured.

MovieTeller has two minute balances:

- **Processing quota**: used by every job, based on the processed video duration.
- **Narration quota**: used only when `enableSpeech=true`, also based on the processed video duration.

If narration is enabled, the allowed processing window must fit both balances. If narration is disabled, narration balance does not limit the job and is not consumed.

## Plans (seed data)

| code | Processing quota | Narration quota | Max single video | Daily cap |
|------|------------------|-----------------|------------------|-----------|
| `free` | 5 min | 5 min | 3 min | none |
| `lite` | 120 min | 120 min | 15 min | 60 min |
| `pro` | 300 min | 300 min | 30 min | 120 min |
| `max` | 450 min | 450 min | 50 min | 150 min |

Current migration seeds narration quota equal to processing quota. Paid narration packs can later increase narration balance without changing processing quota.

## Create job flow

1. Upload to temp path; `ffprobe` → `source_duration_sec` (30s timeout).
2. Transaction: `upsertUser` → `ensureActiveBillingPeriod` → `resolveProcessingRange` → reserve balances `FOR UPDATE` → `INSERT jobs` (queued).
3. After commit: write disk (`request.json` with `startPoint`/`endPoint`, `workflow.json`).
4. Disk failure: `releaseQuota` + `DELETE jobs` + remove directory.

### Errors

| HTTP | `code` | When |
|------|--------|------|
| 400 | `video_probe_failed` | ffprobe missing/timeout/invalid duration |
| 400 | `plan_quota_exhausted` | Cannot reserve enough processing or narration minutes |
| 503 | `database unavailable` | Postgres unreachable |

## Clipping

- Node computes `endPoint = min(source, plan max, processing remaining, daily remaining)`.
- If `enableSpeech=true`, narration remaining also limits `endPoint`.
- `quota_clip_applied` when `endPoint < source_duration_sec`.
- Python `job_runner` trims to `input/processed.mp4` before `run_full_workflow`; clears `start_point`/`end_point` on the workflow request.

## Reservation and finalize

- `reserved_processing_minutes` on `jobs` and `reserved_minutes` on `user_balances` / `user_daily_usage` at create.
- `reserved_narration_minutes` on `jobs` and `narration_reserved_minutes` on `user_balances` only when `enableSpeech=true`.
- Terminal reconcile: `finalizeBilling` with `WHERE billing_finalized_at IS NULL`.
- **Succeeded**: release reserved, deduct processing remaining, deduct narration remaining when used, add daily consumed, insert `usage_ledger`.
- **Failed/canceled**: release reserved only; ledger `consumed_minutes = 0`.

## API

### `GET /api/usage`

- `records`: `usage_ledger` last 3 days.
- `summary`: processing remaining/consumed, narration remaining/consumed, period boundaries.
- `records`: each record includes processing consumed minutes and narration consumed minutes.

Requires auth; returns 503 without DB.

## Retention

- Jobs: disk first, then `DELETE jobs` (3 days, terminal only).
- `usage_ledger`: independent `DELETE` by `created_at` (3 days).
- `job_study_cards`: `ON DELETE CASCADE` from `jobs`.

## Study cards

- Python still writes HTML to disk; worker upserts `job_study_cards` on success.
- `resolveStudyCardsArtifact`: DB preferred, disk fallback for list/inline/download.
