-- M7e: study cards HTML in Postgres

CREATE TABLE IF NOT EXISTS job_study_cards (
  job_id UUID PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  html TEXT NOT NULL,
  byte_size INT NOT NULL DEFAULT 0,
  stored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_path TEXT
);
