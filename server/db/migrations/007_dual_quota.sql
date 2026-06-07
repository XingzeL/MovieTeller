-- M8: split processing quota and narration quota.

ALTER TABLE plans ADD COLUMN IF NOT EXISTS narration_quota_minutes_per_month INT;
UPDATE plans
SET narration_quota_minutes_per_month = quota_minutes_per_month
WHERE narration_quota_minutes_per_month IS NULL;
ALTER TABLE plans ALTER COLUMN narration_quota_minutes_per_month SET NOT NULL;

ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS narration_remaining_minutes INT;
ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS narration_reserved_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS narration_period_quota_minutes INT;
UPDATE user_balances
SET
  narration_remaining_minutes = COALESCE(narration_remaining_minutes, remaining_minutes),
  narration_period_quota_minutes = COALESCE(narration_period_quota_minutes, period_quota_minutes);
ALTER TABLE user_balances ALTER COLUMN narration_remaining_minutes SET NOT NULL;
ALTER TABLE user_balances ALTER COLUMN narration_period_quota_minutes SET NOT NULL;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS reserved_processing_minutes INT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS reserved_narration_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS narration_required BOOLEAN NOT NULL DEFAULT false;
UPDATE jobs
SET reserved_processing_minutes = COALESCE(reserved_processing_minutes, reserved_minutes);
ALTER TABLE jobs ALTER COLUMN reserved_processing_minutes SET NOT NULL;

ALTER TABLE usage_ledger ADD COLUMN IF NOT EXISTS processing_consumed_minutes INT;
ALTER TABLE usage_ledger ADD COLUMN IF NOT EXISTS narration_consumed_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE usage_ledger ADD COLUMN IF NOT EXISTS narration_remaining_after INT;
UPDATE usage_ledger
SET processing_consumed_minutes = COALESCE(processing_consumed_minutes, consumed_minutes);
ALTER TABLE usage_ledger ALTER COLUMN processing_consumed_minutes SET NOT NULL;
