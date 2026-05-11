-- db-patch-001.sql
-- Apply to existing Supabase instance (cannot re-run full db-schema.sql on existing DB).
-- Run in: Supabase Dashboard → SQL Editor → New query → paste → Run.
--
-- All statements are safe on a live system EXCEPT Gap 1 — read the warning below.

-- ── Pre-flight check ─────────────────────────────────────────────────────────
-- Run this first. Must return 0 before applying Gap 1.
-- SELECT COUNT(*) AS rows_with_q35 FROM user_profiles_extended WHERE alert_sensitivity = 'q35';

-- ── Gap 1: Fix alert_sensitivity CHECK (q35 → q75) ───────────────────────────
-- ⚠️  Only safe if rows_with_q35 = 0 from pre-flight check above.
-- q35 did not exist in risk_calibration.json. q75 (least sensitive) was missing.
ALTER TABLE user_profiles_extended
  DROP CONSTRAINT IF EXISTS user_profiles_extended_alert_sensitivity_check;
ALTER TABLE user_profiles_extended
  ADD CONSTRAINT user_profiles_extended_alert_sensitivity_check
    CHECK (alert_sensitivity IN ('q25', 'q50', 'q75'));

-- ── Gap 2: Service role grants ────────────────────────────────────────────────
-- ✅ Safe — purely additive, no-op if already granted.
GRANT ALL ON TABLE users TO service_role;
GRANT ALL ON TABLE coaching_sessions TO service_role;
GRANT ALL ON TABLE coaching_turns TO service_role;

-- ── Gap 3: Index on model_predictions ────────────────────────────────────────
-- ✅ Safe — skips silently if already present.
CREATE INDEX IF NOT EXISTS idx_model_predictions_user_ts
  ON model_predictions (user_id, ts DESC);

-- ── Gap 4: pgvector IVFFlat indexes ──────────────────────────────────────────
-- ✅ Safe — additive only. lists=10 suits small dev datasets.
-- Improves match_past_sessions RPC and scenario search at scale.
CREATE INDEX IF NOT EXISTS idx_coaching_sessions_embedding
  ON coaching_sessions USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX IF NOT EXISTS idx_scenarios_embedding
  ON scenarios USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
