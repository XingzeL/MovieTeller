-- M7a: duration, quota snapshot, reservation, billing finalize marker

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_duration_sec INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS processed_duration_sec INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS quota_clip_applied BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS quota_policy JSONB;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS reserved_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS reserved_usage_date DATE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS billing_finalized_at TIMESTAMPTZ;
