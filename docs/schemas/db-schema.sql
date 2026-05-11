-- ASD System — Supabase schema
-- Run via Supabase SQL editor or migration script

CREATE EXTENSION IF NOT EXISTS vector;

-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  age_group TEXT CHECK (age_group IN ('child', 'teen', 'adult')),
  preferred_language TEXT DEFAULT 'en'
);

-- Caregivers
CREATE TABLE caregivers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- User-caregiver links
CREATE TABLE user_caregiver_links (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  caregiver_id UUID REFERENCES caregivers(id) ON DELETE CASCADE,
  linked_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, caregiver_id)
);

-- Signal samples (Layer 1 ingest — wearable-agnostic)
CREATE TABLE signal_samples (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL,
  signal_type TEXT NOT NULL,
  value FLOAT NOT NULL,
  unit TEXT NOT NULL,
  source TEXT NOT NULL
);
CREATE INDEX ON signal_samples (user_id, ts DESC);

-- Model predictions (Layer 1 output)
CREATE TABLE model_predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ DEFAULT now(),
  risk_score FLOAT NOT NULL,
  cause_tags TEXT[] NOT NULL,
  shap_values JSONB,
  model_version TEXT NOT NULL
);
CREATE INDEX ON model_predictions (user_id, ts DESC);

-- DEPRECATED: replaced by alert_events (see Layer 2 additions below). Kept for reference only.
CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  caregiver_id UUID REFERENCES caregivers(id),
  ts TIMESTAMPTZ DEFAULT now(),
  severity TEXT CHECK (severity IN ('low', 'medium', 'high')),
  risk_score FLOAT,
  cause_tags TEXT[],
  narrative TEXT,
  acknowledged BOOLEAN DEFAULT false,
  false_alarm BOOLEAN DEFAULT false,
  acknowledged_at TIMESTAMPTZ
);

-- Coaching sessions (Layer 3)
CREATE TABLE coaching_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  scenario_id TEXT NOT NULL,
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  turn_count INT DEFAULT 0,
  max_turns INT DEFAULT 12,
  avg_score FLOAT,
  domain TEXT,
  difficulty INT,
  summary TEXT,
  summary_embedding VECTOR(384),
  completed BOOLEAN DEFAULT false
);
CREATE INDEX ON coaching_sessions (user_id, started_at DESC);
CREATE INDEX idx_coaching_sessions_embedding ON coaching_sessions
  USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 10);

-- Scenarios (Layer 3 — pgvector index for content search)
CREATE TABLE scenarios (
  scenario_id TEXT PRIMARY KEY,
  version INT NOT NULL DEFAULT 1,
  embedding VECTOR(384),
  metadata JSONB,
  indexed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_scenarios_embedding ON scenarios
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

-- Coaching turns (Layer 3)
CREATE TABLE coaching_turns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES coaching_sessions(id) ON DELETE CASCADE,
  turn_number INT NOT NULL,
  user_text TEXT NOT NULL,
  persona_reply TEXT NOT NULL,
  critic_json JSONB NOT NULL,
  intent_class TEXT,
  ts TIMESTAMPTZ DEFAULT now()
);

-- Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_samples ENABLE ROW LEVEL SECURITY;
ALTER TABLE coaching_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE coaching_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_data" ON users
  FOR ALL USING (auth.uid() = id);

CREATE POLICY "users_own_signals" ON signal_samples
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "users_own_sessions" ON coaching_sessions
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "users_own_turns" ON coaching_turns
  FOR ALL USING (
    session_id IN (
      SELECT id FROM coaching_sessions WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "caregivers_own_alerts" ON alerts
  FOR SELECT USING (auth.uid() = caregiver_id);

-- ── Layer 2 additions ────────────────────────────────────────────────────

-- Alert events (L2 output — richer than the legacy alerts table)
CREATE TABLE alert_events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
  severity            TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
  risk_score          FLOAT NOT NULL,
  cause_tags          TEXT[] NOT NULL DEFAULT '{}',
  shap_values         JSONB NOT NULL DEFAULT '{}',
  features            JSONB NOT NULL DEFAULT '{}',
  rule_id             TEXT NOT NULL,
  headline            TEXT NOT NULL,
  person_msg          TEXT NOT NULL,
  caregiver_msg       TEXT NOT NULL,
  recommended_actions TEXT[] NOT NULL DEFAULT '{}',
  why_narrative       TEXT,
  acknowledged        BOOLEAN NOT NULL DEFAULT FALSE,
  acknowledged_by     TEXT,
  false_alarm         BOOLEAN NOT NULL DEFAULT FALSE,
  demo                BOOLEAN NOT NULL DEFAULT FALSE,
  cooldown_until      TIMESTAMPTZ,
  ts                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON alert_events (user_id, ts DESC);
CREATE INDEX ON alert_events (user_id, severity);

-- False alarm logs — stores full feature snapshot for threshold recalibration
CREATE TABLE alert_false_alarms (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id              UUID REFERENCES alert_events(id) ON DELETE CASCADE,
  user_id               UUID REFERENCES users(id) ON DELETE CASCADE,
  reported_by           TEXT NOT NULL CHECK (reported_by IN ('user', 'caregiver')),
  reported_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  risk_score_at_alert   FLOAT NOT NULL,
  cause_tags_at_alert   TEXT[] NOT NULL DEFAULT '{}',
  shap_values_at_alert  JSONB NOT NULL DEFAULT '{}',
  all_features_at_alert JSONB NOT NULL DEFAULT '{}',
  rule_id_fired         TEXT NOT NULL,
  notes                 TEXT
);

-- User notification preferences (additive — no L3 tables modified)
CREATE TABLE user_profiles_extended (
  user_id                   UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  phone_number              TEXT,
  emergency_contact_name    TEXT,
  emergency_contact_phone   TEXT,
  emergency_contact_email   TEXT,
  notify_emergency_on       TEXT NOT NULL DEFAULT 'high_only'
                              CHECK (notify_emergency_on IN ('high_only', 'all_alerts', 'none')),
  notify_self_on            TEXT NOT NULL DEFAULT 'all_alerts'
                              CHECK (notify_self_on IN ('all_alerts', 'none')),
  alert_sensitivity         TEXT NOT NULL DEFAULT 'q25'
                              CHECK (alert_sensitivity IN ('q25', 'q50', 'q75'))
);

-- RLS
ALTER TABLE alert_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_false_alarms ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles_extended ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_alerts" ON alert_events
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "users_own_false_alarms" ON alert_false_alarms
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "users_own_profile_extended" ON user_profiles_extended
  FOR ALL USING (auth.uid() = user_id);

-- Service role grants (required for server-side writes bypassing RLS)
GRANT ALL ON TABLE alert_events TO service_role;
GRANT ALL ON TABLE alert_false_alarms TO service_role;
GRANT ALL ON TABLE user_profiles_extended TO service_role;
GRANT ALL ON TABLE users TO service_role;
GRANT ALL ON TABLE coaching_sessions TO service_role;
GRANT ALL ON TABLE coaching_turns TO service_role;

-- ── Memory retrieval RPC — pgvector cosine similarity on session summaries
CREATE OR REPLACE FUNCTION match_past_sessions(
  query_embedding VECTOR(384),
  match_user_id UUID,
  match_domain TEXT,
  match_threshold FLOAT DEFAULT 0.40,
  match_count INT DEFAULT 3
)
RETURNS TABLE (
  id UUID,
  scenario_id TEXT,
  summary TEXT,
  avg_score FLOAT,
  similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    cs.id,
    cs.scenario_id,
    cs.summary,
    cs.avg_score,
    1 - (cs.summary_embedding <=> query_embedding) AS similarity
  FROM coaching_sessions cs
  WHERE cs.user_id = match_user_id
    AND cs.domain = match_domain
    AND cs.completed = true
    AND cs.summary_embedding IS NOT NULL
    AND 1 - (cs.summary_embedding <=> query_embedding) >= match_threshold
  ORDER BY cs.summary_embedding <=> query_embedding, cs.started_at DESC
  LIMIT match_count;
END;
$$;
