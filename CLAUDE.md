# CLAUDE.md

Read this file fully before every session.

In all interactions and commit messages, be concise and sacrifice grammar for the sake of concision.

## Project
Three-layer AI system for autistic individuals and caregivers. Each layer is independent and incrementally improvable. Build order: L3 (complete) → L1 → L2.

- **L1** — Physiological stress escalation predictor (ML → ONNX)
- **L2** — Real-time intervention engine (YAML rules + LLM narrative + notifications)
- **L3** — Social coaching chatbot (Modular RAG + LangChain) ← **COMPLETE**

---

## Non-negotiables
- Python 3.11.9 only — never suggest 3.12+
- `pathlib.Path` for all Python file paths — never string concatenation
- L3 LLM prompts never contain L1/L2 physiological data — air gap is prompt-level
- YAML rules always override ML in L2 — deterministic floor
- All UI labels: "stress escalation risk" — never "meltdown prediction"
- WCAG 2.2 AA minimum — palette `#F7F5F1`, no saturated reds, no auto-sound
- Distress check always runs first in L3 — never reorder
- Critic JSON schema (L3) is additive — UI uses optional chaining always
- safe_response screen (L3) is full-page replace — never a modal
- Person never sees raw risk_score — gentle actionable message only

---

## Environment
- Node 18+, PowerShell, Windows
- Venv: `.venv` in project root

```powershell
# Python API
pip install --upgrade pip wheel setuptools
pip install numpy==1.26.4 scipy
pip install -r apps/api/requirements.txt
.venv\Scripts\activate
uvicorn apps.api.main:app --reload --port 8000

# L1 ML pipeline (separate from API — run once when building L1)
pip install -r ml/requirements.txt   # includes cvxopt (needs C++ Build Tools)
```

```bash
# Frontend
npm install && npm run dev        # localhost:3000
npm run build && npm run lint

# Scripts
python scripts/index_scenarios.py    # L3 — upserts changed scenarios to pgvector
python scripts/run_ml_pipeline.py    # L1 — end-to-end training pipeline
```

---

## Repo structure

```
/
├── CLAUDE.md
├── SETUP.md                          # env vars, deps, Windows setup
├── docs/
│   ├── ARCHITECTURE.md               # 3-layer flow, contracts, constraints
│   ├── DECISIONS.md                  # locked + confirmed decisions, clinical refs
│   ├── VISION.md                     # product vision
│   ├── schemas/
│   │   └── db-schema.sql             # full Supabase DDL
│   └── specs/
│       ├── L1-PREDICT.md             # Layer 1 full spec
│       ├── L2-INTERVENE.md           # Layer 2 full spec
│       └── L3-COACH.md               # Layer 3 full spec (complete)
├── apps/
│   ├── web/                          # Next.js 14 App Router (Tailwind + shadcn/ui)
│   │   ├── app/
│   │   │   ├── (user)/               # L3 user routes (complete)
│   │   │   │   └── coaching/
│   │   │   │       ├── page.tsx                     # scenario selection
│   │   │   │       ├── [sessionId]/page.tsx          # active coaching session
│   │   │   │       └── [sessionId]/summary/page.tsx  # session summary
│   │   │   ├── (caregiver)/          # L2 caregiver routes
│   │   │   │   ├── dashboard/page.tsx                # risk monitor + alert feed
│   │   │   │   ├── alerts/page.tsx                   # alert history
│   │   │   │   └── profile/page.tsx                  # emergency contact + prefs
│   │   │   ├── auth/
│   │   │   │   ├── page.tsx                          # magic link login
│   │   │   │   └── callback/route.ts                 # Supabase auth callback
│   │   │   └── safe-response/page.tsx                # distress screen (full-page replace)
│   │   ├── components/
│   │   │   ├── coaching/             # chat-area, chat-input, chat-message, critic-feedback, scenario-*
│   │   │   ├── layout/               # sidebar
│   │   │   └── ui/                   # shadcn/ui primitives (button, card, badge, input, …)
│   │   ├── hooks/
│   │   │   └── use-user.ts
│   │   └── lib/
│   │       ├── api.ts
│   │       ├── constants.ts
│   │       ├── types.ts
│   │       └── supabase/             # client.ts, server.ts, middleware.ts
│   └── api/                          # FastAPI + Uvicorn + Pydantic v2
│       ├── chains/                   # LangChain LCEL chains (L3)
│       ├── prompts/                  # prompt templates (L3)
│       ├── routers/
│       │   ├── coach.py              # L3 — /coach/*
│       │   ├── predict.py            # L1 — /predict/stream, /predict/scenario/*
│       │   ├── alerts.py             # L2 — /alerts/*
│       │   └── coordinator.py        # Routes L1→L2, L2→notifications. Never L1/L2→L3.
│       ├── config.py
│       ├── db.py
│       ├── embeddings.py
│       ├── safety.py
│       └── main.py
├── ml/                               # L1 offline training
│   ├── data/                         # gitignored
│   │   ├── raw/                      # Engagnition CSVs (Baseline P01-P19, LPE P20-P38, HPE P39-P57)
│   │   ├── canonical/                # per-participant Parquet (per participant×condition)
│   │   └── features/                 # feature_matrix_v1.parquet (training input)
│   ├── adapters/
│   │   ├── base_adapter.py           # abstract base — all future adapters extend this
│   │   └── engagnition_v1.py         # reads Engagnition CSVs → canonical Parquet
│   ├── schema/
│   │   └── canonical_v1.py           # Pydantic canonical schema v1.0
│   ├── preprocessing/
│   │   ├── normalise.py              # per-subject z-score from baseline condition
│   │   ├── artifact_gate.py          # Kleckner 2018 motion artifact gating
│   │   └── eda_decompose.py          # NeuroKit2 phasic/tonic EDA decomposition
│   ├── features/
│   │   ├── window.py                 # window generator (size/stride as params)
│   │   ├── extract.py                # feature extraction per window (no resampling)
│   │   └── label.py                  # intervention-derived label construction
│   ├── training/
│   │   ├── train.py                  # multi-algo, participant-stratified CV
│   │   ├── evaluate.py               # AUROC + F1
│   │   ├── ensemble.py               # soft voting if triggered
│   │   └── calibrate_thresholds.py   # derives L2 YAML risk_score_gte from data
│   ├── export/
│   │   └── to_onnx.py                # winner model → ONNX
│   ├── models/                       # gitignored except committed files below
│   │   ├── feature_schema.json       # committed — inference feature list + exclusions
│   │   └── risk_calibration.json     # committed — q25/q50/q75 thresholds
│   └── experiments/                  # MLflow local tracking (gitignored)
│       └── mlruns/
├── content/                          # L3 source of truth — git-versioned, LangChain reads
│   ├── scenarios/
│   │   ├── sensory_001.md … sensory_008.md
│   │   ├── social_001.md … social_012.md
│   │   └── workplace_001.md … workplace_010.md
│   ├── rubrics/
│   │   ├── sensory_advocacy.md
│   │   ├── social_advanced.md
│   │   ├── social_basic.md
│   │   └── workplace_communication.md
│   ├── personas/
│   │   ├── barista_rushed.md
│   │   ├── colleague_friendly.md
│   │   ├── friend_casual.md
│   │   ├── interviewer_formal.md
│   │   ├── shop_assistant.md
│   │   ├── stranger_helpful.md
│   │   └── teacher_patient.md
│   ├── safety/
│   │   ├── distress_keywords.yaml
│   │   └── safe_response.md
│   └── schema/
│       └── scenario_schema.md
├── rules/
│   └── intervention_rules.yaml       # L2 YAML rules — thresholds from risk_calibration.json
└── scripts/
    ├── index_scenarios.py            # L3 — upserts changed scenarios to pgvector
    └── run_ml_pipeline.py            # L1 — orchestrates full training pipeline
```

---

## Tech stack

| Layer | Key choices |
|---|---|
| L3 | Groq (Llama 3.3 70B), Gemini 2.5 Flash-Lite (fallback), LangChain LCEL, pgvector, all-MiniLM-L6-v2, LangSmith |
| L1 | Polars, Parquet/pyarrow, DVC, NeuroKit2, XGBoost/LightGBM/sklearn, imbalanced-learn, ONNX, MLflow |
| L2 | YAML rules, Groq (25-word narrative), Twilio (SMS), Resend (email), Upstash Redis (narrative cache) |
| Shared | FastAPI + Pydantic v2, Next.js 14, Tailwind + shadcn/ui, Supabase (Postgres + Auth + Realtime + pgvector), Vercel, Render, Sentry |

---

## Layer contracts (do not break)

```
L1 → L2:  {risk_score: float, cause_tags: str[], shap_values: dict, features: dict, ts: datetime, user_id: str, demo: bool}
L2 → UI:  {alert_id, severity, person_message, caregiver_message, recommended_actions, app_actions, cooldown_until}
L3 → UI:  {intent, persona_reply, critic: {score, suggestion}, turn_number, turns_remaining, session_complete}
```

---

## Content status (L3)

| Path | Status |
|---|---|
| `/content/rubrics/` | COMPLETE — 4 files |
| `/content/safety/` | COMPLETE — 2 files |
| `/content/schema/scenario_schema.md` | COMPLETE |
| `/content/scenarios/` | COMPLETE — 30 files |
| `/content/personas/` | COMPLETE — 7 files |

---

## Build sessions

| Session | Goal | Read first |
|---|---|---|
| 0 | Accounts + local env setup | CLAUDE.md + SETUP.md |
| 1 | Repo scaffold + L3 content + DB migration | L3-COACH.md |
| 2 | L3 FastAPI backend + LangChain pipeline | L3-COACH.md |
| 3 | pgvector indexing + cross-session memory | L3-COACH.md |
| 4 | Next.js L3 coaching UI | L3-COACH.md |
| 5 | L3 demo + caregiver dashboard scaffold | L2-INTERVENE.md |
| 6 | L1 ML pipeline: adapter + preprocessing + features | L1-PREDICT.md |
| 7 | L1 training: multi-algo + CV + calibration + ONNX | L1-PREDICT.md |
| 8 | L2 rule engine + alert API + notifications | L2-INTERVENE.md |
| 9 | L2 demo SSE stream + caregiver dashboard complete | L2-INTERVENE.md |
| 10 | User profile extension + person-facing alerts + false alarm logging | L2-INTERVENE.md |
