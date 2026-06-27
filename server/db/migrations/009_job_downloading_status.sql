-- Allow remote URL download stage before pipeline queue

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_status_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_status_check CHECK (
  status IN (
    'downloading',
    'queued',
    'running',
    'canceling',
    'succeeded',
    'failed',
    'canceled'
  )
);
