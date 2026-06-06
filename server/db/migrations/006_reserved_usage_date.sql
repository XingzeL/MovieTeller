-- M7 billing: remember the usage date used for quota reservation.

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS reserved_usage_date DATE;
