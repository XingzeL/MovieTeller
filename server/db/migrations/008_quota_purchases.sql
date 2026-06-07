-- M8b: purchased quota bonuses, per-video override, purchase ledger.

ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS bonus_processing_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS bonus_narration_minutes INT NOT NULL DEFAULT 0;
ALTER TABLE user_balances ADD COLUMN IF NOT EXISTS max_video_duration_sec_override INT;

CREATE TABLE IF NOT EXISTS quota_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL CHECK (kind IN ('plan', 'addon')),
  product_id TEXT NOT NULL,
  processing_minutes INT NOT NULL DEFAULT 0,
  narration_minutes INT NOT NULL DEFAULT 0,
  max_video_duration_sec INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS quota_purchases_user_created_idx
  ON quota_purchases (user_id, created_at DESC);

-- Backfill bonus pools for balances already topped up before 008.
UPDATE user_balances
SET
  bonus_processing_minutes = GREATEST(
    bonus_processing_minutes,
    GREATEST(0, remaining_minutes - period_quota_minutes)
  ),
  bonus_narration_minutes = GREATEST(
    bonus_narration_minutes,
    GREATEST(0, narration_remaining_minutes - narration_period_quota_minutes)
  )
WHERE remaining_minutes > period_quota_minutes
   OR narration_remaining_minutes > narration_period_quota_minutes;

-- Free-tier users with purchased bonus get Lite single-video cap (15 min).
UPDATE user_balances ub
SET max_video_duration_sec_override = 900
FROM user_subscriptions us
JOIN plans p ON p.id = us.plan_id
WHERE ub.user_id = us.user_id
  AND us.status = 'active'
  AND p.code = 'free'
  AND ub.bonus_processing_minutes > 0
  AND COALESCE(ub.max_video_duration_sec_override, 0) < 900;
