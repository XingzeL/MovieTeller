-- Phase 2 Lite: jobs control plane (see docs/reference/phase2-lite.md)

CREATE TABLE IF NOT EXISTS jobs (
  job_id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('queued', 'running', 'canceling', 'succeeded', 'failed', 'canceled')
  ),
  attempt_id INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  output_root TEXT NOT NULL,
  input_video_path TEXT NOT NULL,
  claimed_at TIMESTAMPTZ,
  claimed_by TEXT,
  last_heartbeat_at TIMESTAMPTZ,
  cancel_requested_at TIMESTAMPTZ,
  cancel_acknowledged_at TIMESTAMPTZ,
  cancel_deadline_at TIMESTAMPTZ,
  canceled_at TIMESTAMPTZ,
  cancel_mode TEXT CHECK (cancel_mode IS NULL OR cancel_mode IN ('cooperative', 'forced')),
  error_code TEXT,
  error_message TEXT,
  retryable BOOLEAN NOT NULL DEFAULT false,
  original_source JSONB,
  video_downloaded_at TIMESTAMPTZ,
  video_purged_at TIMESTAMPTZ,
  video_state_version INTEGER NOT NULL DEFAULT 0,
  current_stage TEXT,
  progress JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS jobs_user_updated_idx ON jobs (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs (status, created_at);
