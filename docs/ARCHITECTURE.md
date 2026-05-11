# Architecture Overview

Three independent layers. Each layer is self-contained and incrementally improvable without affecting the others.

```
┌─────────────────────────────────────────────────┐
│  Layer 3 — Social Coaching Chatbot  [COMPLETE]  │
│  Modular RAG + LangChain LCEL                   │
│  User ↔ persona roleplay + real-time critic     │
│  Content: /content/ (Markdown, git-versioned)   │
│  Memory: Supabase Postgres + pgvector           │
└─────────────────────────────────────────────────┘
         ▲ AIR GAP — L3 LLM prompts never contain L1/L2 data
─────────┼────────────────────────────────────────
         │
┌────────┴────────────────────────────────────────┐
│  Layer 2 — Intervention Engine                  │
│  YAML rules (deterministic floor)               │
│  + LLM narrative (Groq, 25 words)               │
│  Input: risk_score + cause_tags + features      │
│  Output: alert → person + emergency contact     │
│          + caregiver (Supabase Realtime)         │
└─────────────────────────────────────────────────┘
         ▲
┌────────┴────────────────────────────────────────┐
│  Layer 1 — Stress Escalation Predictor          │
│  Offline: multi-algo training → best → ONNX     │
│  Online: synthetic demo mode (no wearable)      │
│  Data: Engagnition dataset (Empatica E4)        │
│  Output: risk_score (0-1) + SHAP cause_tags[]   │
└─────────────────────────────────────────────────┘
```

## Inter-layer contracts

**L1 → L2:**
`{risk_score: float 0-1, cause_tags: string[], shap_values: object, features: object, ts: datetime}`

**L2 → UI (person + emergency contact + caregiver):**
`{alert_id, severity, person_message, caregiver_message, recommended_actions, app_actions, cooldown_until}`
Full schema in docs/specs/L2-INTERVENE.md.

**L3 → User UI:**
`{intent, persona_reply, critic: {score, suggestion}, turn_number, turns_remaining, session_complete}`
Critic schema is additive — UI must use optional chaining on all fields.

## Coordinator

`apps/api/routers/coordinator.py` — reads state from all layers, routes directionally only:

```
L1 output → L2 (risk processing)
L2 output → person (self-alert) + emergency contact + caregiver UI
L3 output → user UI (coaching feedback)
```

UI shell may read state from all layers. Air gap is enforced at the **prompt level** — L3 LLM context never contains physiological data regardless of what the coordinator or UI shell can access.

## Notification recipients

L2 alerts go to up to three recipients in parallel:
- **Person themselves** — gentler, self-directed language; in-app + SMS + email
- **Emergency contact** — informational; SMS + email (severity threshold configurable)
- **Caregiver (if registered)** — Supabase Realtime + web-push + email digest

## False alarm feedback loop

False alarm reports store the full feature vector at time of alert. This data feeds threshold recalibration after each model retrain. Caregivers and the person themselves can both report false alarms.

## ML pipeline (L1 offline)

```
Raw CSVs → Source Adapter → Canonical Parquet (per participant×condition)
         → Feature Extraction (window-based, no cross-signal resampling)
         → Label Construction (intervention-derived)
         → Multi-algo training → Best model → ONNX
         → Threshold calibration → risk_calibration.json → L2 YAML
```

Future datasets: write a new adapter extending `BaseAdapter`. Training code unchanged.

## Key constraints
- L3 air-gapped from L1/L2 at prompt level — never at code level
- YAML rules in L2 always override ML output — deterministic floor
- All UI labels: "stress escalation risk" — never "meltdown prediction"
- Person never sees their own risk_score — only gentle actionable messages
- Window size, stride, lookahead are hyperparameters — verified on data, not hardcoded
- Full DB schema: docs/schemas/db-schema.sql
- All decisions: docs/DECISIONS.md
