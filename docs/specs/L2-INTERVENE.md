# L2 — Intervention Engine

## Status: Ready to build (Session 8–10)

---

## Input

From L1 coordinator:
```json
{
  "risk_score": 0.73,
  "cause_tags": ["internal_arousal", "motor_agitation"],
  "shap_values": {},
  "features": {},
  "ts": "...",
  "user_id": "uuid",
  "demo": false
}
```

---

## Logic

YAML rules always run first — deterministic floor. ML output can add context but never override rules.

```
1. Load risk_calibration.json → get current risk_score_gte thresholds
2. Match cause_tags + risk_score against rules/intervention_rules.yaml
3. Select highest-severity matching rule
4. Generate LLM "why" narrative (Groq, 25 words, cached in Redis)
5. Build alert payload
6. Fire notifications in parallel (person + emergency contact + caregiver)
7. Log alert_event to DB (full features stored)
8. Start cooldown
```

---

## Rule file

`rules/intervention_rules.yaml` — thresholds populated from `ml/models/risk_calibration.json` after each retrain. Do not hardcode threshold values.

```yaml
meta:
  model_version: "v1.0"
  calibrated_at: ""
  default_threshold: 0.0    # populated from risk_calibration.json q25

rules:
  - id: motor_agitation_elevated
    condition:
      cause_tags_include: ["motor_agitation"]
      risk_score_gte: 0.0   # populated from calibration
    severity: medium
    person_message: "You might be feeling restless. Finding a quieter space or a short movement break could help."
    caregiver_message: "Physical agitation detected. A movement break or quieter environment may help."
    recommended_actions:
      - "Offer a short movement break"
      - "Reduce immediate task demands"
      - "Move to a less crowded space if possible"
    cooldown_minutes: 10

  - id: internal_arousal_sustained
    condition:
      cause_tags_include: ["internal_arousal", "escalating_arousal"]
      risk_score_gte: 0.0
    severity: medium
    person_message: "Your body may be feeling stressed. Taking a few slow breaths or stepping away briefly might help."
    caregiver_message: "Sustained physiological arousal detected. Calm, low-demand check-in recommended."
    recommended_actions:
      - "Calm, low-demand check-in"
      - "Avoid requiring verbal responses right now"
      - "Suggest slow breathing or a grounding activity"
    cooldown_minutes: 10

  - id: physiological_stress_elevated
    condition:
      cause_tags_include: ["physiological_stress", "above_personal_baseline"]
      risk_score_gte: 0.0
    severity: medium
    person_message: "You seem to be above your usual stress level. Giving yourself a moment away might help."
    caregiver_message: "Signals are significantly above this person's personal baseline."
    recommended_actions:
      - "Check environment for sensory triggers"
      - "Offer sensory tools if available (headphones, sunglasses)"
    cooldown_minutes: 12

  - id: full_escalation_urgent
    condition:
      risk_score_gte: 0.0   # populated from q90
    severity: high
    person_message: "You may be getting very overwhelmed. Please try to find a quiet spot. Your emergency contact is being notified."
    caregiver_message: "High escalation risk. Immediate calm, supportive presence recommended. Do not demand verbal responses."
    recommended_actions:
      - "Move to quietest available space immediately"
      - "Reduce all sensory input"
      - "Do not demand verbal responses"
      - "Stay nearby calmly without physical contact unless invited"
    cooldown_minutes: 5

  - id: demo_mode
    condition:
      demo: true
      risk_score_gte: 0.0
    severity: medium
    cooldown_minutes: 0
```

---

## Alert payload

```json
{
  "alert_id": "uuid",
  "user_id": "uuid",
  "severity": "medium",
  "risk_score": 0.73,
  "cause_tags": ["internal_arousal", "motor_agitation"],
  "headline": "Attention may be needed",
  "person_message": "...",
  "caregiver_message": "...",
  "why": "Sustained arousal with elevated physical activity.",
  "recommended_actions": ["..."],
  "app_actions": [
    {"label": "I'm okay — false alarm", "action": "false_alarm"},
    {"label": "Acknowledged", "action": "acknowledge"}
  ],
  "cooldown_until": "...",
  "demo": false,
  "ts": "..."
}
```

---

## Notification delivery

Three parallel notification paths:

**Person (self-alert) — always fires:**
- In-app: Supabase Realtime push to user's active session
- SMS: Twilio (if phone number registered)
- Email: Resend (fallback, always)
- Language: `person_message` from YAML — gentle, self-directed, actionable

**Emergency contact — fires on severity=high OR user opt-in to "all alerts":**
- SMS: Twilio
- Email: Resend

**Caregiver (if registered and linked):**
- Supabase Realtime WebSocket → dashboard live feed
- Web-push VAPID → browser notification when tab inactive
- Email digest: Resend (daily summary, non-urgent)

**Demo mode:** in-app Realtime only. No SMS, no external email. Cooldown=0.

---

## LLM narrative

Generates `why` field only. All other message fields are YAML-authored.

- Model: Groq Llama 3.3 70B, max 25 words
- Cache: Upstash Redis, key = `cause_tags_hash`, TTL = 24h
- Fallback: `"Physiological stress signals elevated."` if Groq unavailable

---

## False alarm logging

Both the person and caregiver can report false alarms. Full parameter snapshot stored on every report.

```
alert_false_alarms table:
  alert_id, user_id, reported_by ("user"|"caregiver")
  reported_at
  risk_score_at_alert
  cause_tags_at_alert
  shap_values_at_alert
  all_features_at_alert     ← complete feature vector
  rule_id_fired
  notes (optional free text)
```

Threshold recalibration trigger: if false alarm rate > 20% on a rule → raise that rule's threshold. If overall false alarm rate > 20% → raise default from q25 to q35. Recalibrate after every 50 reports.

---

## User profile additions

New fields on existing user profile (additive — no L3 tables modified):

```
phone_number               (E.164 format)
emergency_contact_name
emergency_contact_phone    (E.164 format)
emergency_contact_email
notify_emergency_on        "high_only" | "all_alerts" | "none"
notify_self_on             "all_alerts" | "none"
```

Collected at registration. Both fields optional but recommended. Magic link auth flow unchanged.

---

## DB additions (additive only)

```sql
CREATE TABLE alert_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES auth.users(id),
  severity         TEXT NOT NULL,
  risk_score       FLOAT NOT NULL,
  cause_tags       TEXT[] NOT NULL,
  shap_values      JSONB NOT NULL,
  features         JSONB NOT NULL,
  rule_id          TEXT NOT NULL,
  headline         TEXT NOT NULL,
  person_msg       TEXT NOT NULL,
  caregiver_msg    TEXT NOT NULL,
  recommended_actions TEXT[] NOT NULL,
  why_narrative    TEXT,
  acknowledged     BOOLEAN DEFAULT FALSE,
  acknowledged_by  TEXT,
  false_alarm      BOOLEAN DEFAULT FALSE,
  demo             BOOLEAN DEFAULT FALSE,
  cooldown_until   TIMESTAMPTZ,
  ts               TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alert_false_alarms (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id              UUID REFERENCES alert_events(id),
  user_id               UUID REFERENCES auth.users(id),
  reported_by           TEXT NOT NULL,
  reported_at           TIMESTAMPTZ DEFAULT NOW(),
  risk_score_at_alert   FLOAT NOT NULL,
  cause_tags_at_alert   TEXT[] NOT NULL,
  shap_values_at_alert  JSONB NOT NULL,
  all_features_at_alert JSONB NOT NULL,
  rule_id_fired         TEXT NOT NULL,
  notes                 TEXT
);

CREATE TABLE user_profiles_extended (
  user_id                   UUID PRIMARY KEY REFERENCES auth.users(id),
  phone_number              TEXT,
  emergency_contact_name    TEXT,
  emergency_contact_phone   TEXT,
  emergency_contact_email   TEXT,
  notify_emergency_on       TEXT DEFAULT 'high_only',
  notify_self_on            TEXT DEFAULT 'all_alerts'
);
```

---

## API endpoints

```
POST /alerts/trigger
     body: L1 output payload
     returns: {alert_id, severity, person_message, caregiver_message, recommended_actions}

POST /alerts/{alert_id}/acknowledge
     body: {acknowledged_by: "user"|"caregiver"}

POST /alerts/{alert_id}/false-alarm
     body: {reported_by: "user"|"caregiver", notes?: str}
     Stores full feature snapshot.

GET  /alerts/{user_id}
     params: limit?, offset?, severity?

GET  /alerts/{alert_id}/detail
     returns full payload including features (caregiver-only)
```

---

## Caregiver dashboard UI

`app/(caregiver)/dashboard/page.tsx` — additions to existing scaffold:

**RiskMonitorPanel**
Arc gauge 0→1 with colour zones (green/amber/red). Cause tag chips update every 5s via SSE. Demo scenario selector: calm / escalating / rapid spike. "Demo Mode" label always visible when active.

**SignalChartPanel**
Three sparklines (GSR, ACC SVM, Skin Temp), 60s rolling window, SSE-driven. Synthetic values in demo mode. GSR phasic peaks marked as dots.

**AlertFeed**
Supabase Realtime subscription. Each card: headline, why, recommended_actions, person/caregiver message toggle, Acknowledge and False Alarm buttons. False alarm: optional notes field before submit.

`app/(caregiver)/alerts/page.tsx`
Alert history. Filterable by severity, date, false alarm status. Expandable detail: features at alert time visible to caregiver.

`app/(caregiver)/profile/page.tsx` ← new
Emergency contact registration, phone number, notification preferences, alert sensitivity (maps to q25/q35/q50 threshold selection).

**Person-facing alert (in `app/(user)/` only)**
Persistent banner on any user page when Supabase Realtime fires for that user. Full-page on severity=high. Content: `person_message` only — no risk_score, no cause_tags shown to person. Buttons: "I'm okay" (false alarm) | "Noted, thank you". Never interrupts an active L3 coaching turn — queues and shows after turn completes.

---

## Files to produce

```
rules/intervention_rules.yaml
apps/api/routers/predict.py
apps/api/routers/alerts.py
apps/api/routers/coordinator.py
apps/web/app/(caregiver)/dashboard/page.tsx   (expand existing)
apps/web/app/(caregiver)/alerts/page.tsx      (expand existing)
apps/web/app/(caregiver)/profile/page.tsx     (new)
```
