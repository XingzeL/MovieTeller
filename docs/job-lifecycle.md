# Job Lifecycle Contract

## Status values

`queued` → `running` → `succeeded` | `failed` | `canceled`

On server restart, stale `queued` / `running` jobs are marked `failed` (`server_restarted`).

## Key `workflow.json` fields

| Field | Purpose |
|-------|---------|
| `job_id` | UUID directory name |
| `user_id` | Owner (required for user-visible jobs in multi-user mode) |
| `status` | Lifecycle state |
| `video_downloaded_at` | User downloaded full video (download-once policy) |
| `video_purged_at` | Video file removed by retention |
| `original_source` | Upload metadata for display title |

## Retention

- **Video purge**: After `video_downloaded_at`, scheduler removes video file (recent jobs scan).
- **Full delete**: Jobs older than 3 days (terminal only) — entire directory removed via `purgeOldJobs` + `scanAllJobsForSystem`.

## Artifacts

- User-facing kinds: `renderedVideo`, `studyCardsHtml` (see `artifactManifest.js`).
- `canDownloadVideo` / `canOpenStudyCards` / `videoState` are computed server-side (`jobAvailability.js`).
