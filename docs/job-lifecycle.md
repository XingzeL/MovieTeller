# Job Lifecycle Contract

This document is the **authoritative contract** for Job behavior in Phase 1 (filesystem storage, Cookie session, per-user ACL). Implementation must match; tests and [`jobs-api.md`](./jobs-api.md) cross-reference this file.

## Status machine

```text
queued → running → succeeded | failed | canceled
```

| Transition | Writer | Notes |
|--------------|--------|-------|
| → `queued` | Node | Job directory created; `workflow.json` written after upload |
| → `running` | Python | `job_runner` calls `write_initial(status="running")` |
| → terminal | Python | `succeeded` / `failed` / `canceled` |
| → `canceled` (not spawned) | Node | Job still in memory `waiting` queue only — Node marks canceled directly |
| `cancel_requested_at` | Node | User cancel while spawned; `cancel.flag` + timestamp; Python finishes as `canceled` |

**Server restart (combined mode):** [`recoverJobsOnStartup`](../server/src/services/jobs/jobRecovery.js) marks disk `queued` and `running` jobs as `failed` with `error_code: server_restarted`. This avoids zombie jobs when the in-memory queue is lost.

## `workflow.json` fields (required for user-visible jobs)

| Field | Required | Purpose |
|-------|----------|---------|
| `job_id` | yes | UUID; directory name under `JOBS_ROOT` |
| `user_id` | yes (multi-user) | Owner; must match Cookie session user for ACL |
| `status` | yes | Lifecycle state (see above) |
| `input_video_path` | yes | Path to uploaded source under `input/` |
| `output_root` | yes | Job root directory |
| `created_at` / `updated_at` | yes | ISO timestamps |
| `original_source` | recommended | Display title / remote URL metadata |
| `video_downloaded_at` | nullable | Set when user successfully downloads `renderedVideo` (download-once) |
| `video_purged_at` | nullable | Set when video file removed after download |
| `video_state_version` | yes | Incremented on download mark; clients may use for cache busting |
| `current_stage` / `progress` / `error` | optional | Runtime detail |
| `artifacts` | legacy | **Not used** for product downloads (manifest-only) |

Jobs **without** `user_id` are **invisible** to all users (no list, no detail — same as not found).

## Multi-user access control

- Identity: Cookie `mt_uid` → [`currentUser`](../server/src/middleware/currentUser.js) → `req.user.id`.
- Creation: [`createJob`](../server/src/services/jobs/createJob.js) sets `user_id` from `req.user.id` only; **body `userId` is ignored**.
- Read/write: all Job APIs use [`jobAccess`](../server/src/services/jobs/jobAccess.js) (`*ForUser`).
- Cross-user or wrong owner: **HTTP 404** `{ error: "job not found" }` (same as missing job — no enumeration).

## HTTP semantics (artifacts)

Base path: `/api/jobs/:jobId/artifacts/:kind` (requires owner Cookie).

| kind | Request | Success | Failure (owner) |
|------|---------|---------|-----------------|
| `studyCardsHtml` | attachment download | 200 file | 404 no manifest / missing file |
| `studyCardsHtml` | `?inline=1` or `?inline=true` | 200 HTML inline | 404 |
| `renderedVideo` | attachment download | 200 file; marks `video_downloaded_at`; async video purge | 404 |
| `renderedVideo` | `?inline=1` | **410** `video inline preview is disabled` | — |
| `renderedVideo` | attachment after download or purge | **410** `video already downloaded` | — |

Non-owner: **404** for all of the above.

## Artifacts (manifest-only)

- **Single source:** `{job_root}/artifacts/manifest.json` (written by Python on success).
- Node [`artifactManifest.js`](../server/src/services/jobs/artifactManifest.js) lists/resolves **only** manifest entries for `renderedVideo` and `studyCardsHtml`.
- **No fallback** to `workflow.json` → `artifacts.renderedVideoPath` / `studyCardsHtmlPath` or disk paths under `render/` / `study_cards/`.
- If manifest is missing or kind not listed: no product artifacts (empty list / 404 download).

## Video policy (download-once)

1. While `succeeded` and manifest has `renderedVideo` and not yet downloaded: `videoState=available`, `canDownloadVideo=true`.
2. User downloads via `GET .../artifacts/renderedVideo` (attachment): server sets `video_downloaded_at`, appends audit `job.video_downloaded`, schedules [`purgeVideoForJob`](../server/src/services/jobs/purgeVideo.js).
3. After download (or if already downloaded): repeat download → **410**; UI should use programmatic fetch to show message.
4. Purge removes video file, sets `video_purged_at`; `videoState` becomes `downloaded` or `purged`; `canDownloadVideo=false`.
5. **Study cards** remain available (inline/download) until the whole Job directory is deleted by age retention.

## Study cards policy

- Long-lived relative to video: not removed by video purge.
- Inline preview allowed: `GET .../studyCardsHtml?inline=1` → 200 for owner.
- Removed only when entire job directory deleted (see retention).

## List and retention policy (product decision)

| Decision | Value | Rationale |
|----------|-------|-----------|
| API list limit | `GET /api/jobs?limit=1000` max ([`MAX_LIMIT=1000`](../server/src/services/jobs/listJobs.js)) | Load full recent history per user |
| UI display | All non-expired jobs for user (client may search/filter) | **Not** capped to “8 recent items” in UI |
| Age retention | **3 days** after `created_at` (terminal jobs only) | [`purgeOldJobs`](../server/src/services/jobs/purgeOldJobs.js) deletes **entire** job directory |
| Video purge | After `video_downloaded_at` | Scheduler scans recent jobs; deletes video file only |

Early product notes mentioned showing only 8 history items; **superseded** by limit=1000 + 3-day full-directory cleanup.

## DTO availability fields (server-computed)

From [`jobAvailability.js`](../server/src/services/jobs/jobAvailability.js), exposed on list/detail:

| Field | Meaning |
|-------|---------|
| `videoState` | `not_generated` \| `disabled` (no TTS) \| `available` \| `downloaded` \| `purged` |
| `canDownloadVideo` | `true` only when `videoState === available` |
| `canOpenStudyCards` | `succeeded` and manifest has `studyCardsHtml` |

Clients must not infer download buttons from `status === succeeded` alone.

## Audit events

Append-only: `{job_root}/logs/audit.jsonl` ([`auditLog.js`](../server/src/services/audit/auditLog.js)).

| Event | When |
|-------|------|
| `job.created` | `POST /api/jobs` success |
| `job.video_downloaded` | `renderedVideo` attachment download completes（见 `jobs.js`） |
| `artifact.access` | Other artifact download or study card inline view |
| `job.canceled` | `POST .../cancel` success |
| `job.retried` | `POST .../retry` success |

Each line: `{ schema_version, ts, user_id, job_id, event, detail? }`.

## Runtime modes (reference)

Default development/production single-process: API + in-memory queue + spawn + scheduler ([`bootstrap.js`](../server/src/runtime/bootstrap.js)). Optional split API/worker documented in [`worker-runtime.md`](./worker-runtime.md).

---

See also: [`multi-user-storage-and-transport.md`](./multi-user-storage-and-transport.md), [`jobs-api.md`](./jobs-api.md), [`job-queue-limitations.md`](./job-queue-limitations.md).
