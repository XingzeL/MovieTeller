-- M7b: users, plans, subscriptions, balances, daily usage

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  quota_minutes_per_month INT NOT NULL,
  max_video_duration_sec INT NOT NULL,
  max_daily_minutes INT,
  price_cents_per_month INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT true,
  sort_order INT NOT NULL DEFAULT 0
);

INSERT INTO plans (
  id, code, name, quota_minutes_per_month, max_video_duration_sec,
  max_daily_minutes, price_cents_per_month, is_active, sort_order
) VALUES
  ('free', 'free', 'Free', 5, 180, NULL, 0, true, 0),
  ('lite', 'lite', 'Lite', 120, 900, 60, 2900, true, 1),
  ('pro', 'pro', 'Pro', 300, 1800, 120, 5900, true, 2),
  ('max', 'max', 'Max', 450, 3000, 150, 9900, true, 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id)
SELECT DISTINCT user_id FROM jobs
WHERE user_id IS NOT NULL AND trim(user_id) <> ''
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES users(id),
  plan_id TEXT NOT NULL REFERENCES plans(id),
  status TEXT NOT NULL CHECK (status IN ('active', 'canceled', 'expired')),
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_subscriptions_user_idx ON user_subscriptions (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_balances (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  remaining_minutes INT NOT NULL,
  reserved_minutes INT NOT NULL DEFAULT 0,
  period_quota_minutes INT NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_daily_usage (
  user_id TEXT NOT NULL REFERENCES users(id),
  usage_date DATE NOT NULL,
  consumed_minutes INT NOT NULL DEFAULT 0,
  reserved_minutes INT NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, usage_date)
);

CREATE INDEX IF NOT EXISTS user_daily_usage_user_date_idx ON user_daily_usage (user_id, usage_date DESC);
