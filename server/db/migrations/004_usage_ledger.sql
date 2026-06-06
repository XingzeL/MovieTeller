-- M7c: usage ledger (independent retention from jobs)

CREATE TABLE IF NOT EXISTS usage_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES users(id),
  job_id UUID REFERENCES jobs(job_id) ON DELETE SET NULL,
  job_id_snapshot TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  video_name TEXT,
  source_duration_seconds INT,
  processed_duration_seconds INT,
  consumed_minutes INT NOT NULL DEFAULT 0,
  remaining_after INT,
  status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'canceled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS usage_ledger_job_id_unique_idx
  ON usage_ledger (job_id)
  WHERE job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS usage_ledger_user_created_idx
  ON usage_ledger (user_id, created_at DESC);
