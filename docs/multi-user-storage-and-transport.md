# Multi-User Storage and Transport (Phase 1)

See also [multi-user-readiness-work-items.md](./multi-user-readiness-work-items.md) and [job-lifecycle.md](./job-lifecycle.md).

## Storage

| Layer | What | Where |
|-------|------|--------|
| Session | Current user id | Browser cookie `mt_uid` → `req.user.id` |
| Job owner | Per-job owner | `{JOBS_ROOT}/{jobId}/workflow.json` → `user_id` |
| Options | TTS, languages | `request.json` (not identity) |

No Postgres user table in Phase 1.

## Transport

- **Dev switch user**: `POST /api/dev/session` with `{ "userId": "user-a" }` (non-production only).
- **API calls**: `fetch(..., { credentials: 'include' })` so cookies are sent.
- **Direct browser URLs** (iframe, `<a download>`, `<img>`): same cookie; no custom headers.

Recommended dev setup: Vite proxy (`localhost:5173` → `/api` → `localhost:3001`) so cookies stay same-site.

## ACL

- List: `listJobsForUser` — jobs without matching `user_id` are omitted; legacy jobs with no `user_id` are invisible.
- Detail / artifacts / cancel / retry: `jobAccess` — wrong owner → **404**.
- Retention: `scanAllJobsForSystem` — system-wide scan only; never `listJobsForUser`.
