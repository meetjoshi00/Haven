# Haven

A three-layer AI system for autistic individuals and their caregivers.

- **L3 — Social Coaching Chatbot** — persona roleplay with real-time feedback
- **L2 — Intervention Engine** — YAML rule engine + LLM alert narratives
- **L1 — Stress Escalation Predictor** — physiological ML → ONNX inference

Each layer is self-contained and independently deployable.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  L3 — Social Coaching Chatbot                    │
│  Modular RAG + LangChain LCEL                    │
│  User ↔ persona roleplay + real-time critic      │
└──────────────────────────────────────────────────┘
         ▲ AIR GAP — L3 prompts never contain L1/L2 data
─────────┼───────────────────────────────────────────
┌────────┴─────────────────────────────────────────┐
│  L2 — Intervention Engine                        │
│  YAML rules (deterministic) + Groq narrative     │
│  → alert person + emergency contact + caregiver  │
└──────────────────────────────────────────────────┘
         ▲
┌────────┴─────────────────────────────────────────┐
│  L1 — Stress Escalation Predictor                │
│  XGBoost/LightGBM → ONNX (Empatica E4 wearable) │
│  Output: risk_score (0–1) + SHAP cause_tags[]    │
└──────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Key Tech |
|---|---|
| L3 | Groq (Llama 3.3 70B), Gemini 2.5 Flash-Lite, LangChain LCEL, pgvector, all-MiniLM-L6-v2 |
| L2 | YAML rules, Groq (25-word narrative), Twilio SMS, Resend email, Upstash Redis |
| L1 | Polars, NeuroKit2, XGBoost/LightGBM, ONNX, MLflow |
| Shared | FastAPI + Pydantic v2, Next.js 14 App Router, Tailwind + shadcn/ui, Supabase |

---

## Quick Start

**Prerequisites:** Python 3.11.9, Node 18+, PowerShell (Windows)

```powershell
# Python backend
pip install numpy==1.26.4 scipy
pip install -r apps/api/requirements.txt
cp .env.example .env          # fill in all values
.venv\Scripts\activate
uvicorn apps.api.main:app --reload --port 8000
```

```bash
# Next.js frontend
npm install
npm run dev                   # localhost:3000
```

```bash
# L3 — index scenario content into pgvector (run once after DB setup)
python scripts/index_scenarios.py

# L1 — run full ML training pipeline (run once to generate ONNX model)
python scripts/run_ml_pipeline.py
```

See `SETUP.md` for full environment setup including Supabase, Vercel, and Windows-specific dependencies.

---

## Project Structure

```
apps/
  api/          FastAPI backend (L1 inference, L2 rule engine, L3 coaching)
  web/          Next.js 14 frontend (coaching UI + caregiver dashboard)
ml/             L1 offline training pipeline
content/        L3 scenario content (Markdown, git-versioned)
rules/          L2 intervention rules (YAML)
docs/           Architecture, specs, DB schema
scripts/        ML pipeline + indexing CLI scripts
```

---

## Docs

- `SETUP.md` — full environment setup guide
- `docs/ARCHITECTURE.md` — layer contracts and data flow
- `docs/specs/L1-PREDICT.md` — stress predictor spec
- `docs/specs/L2-INTERVENE.md` — intervention engine spec
- `docs/specs/L3-COACH.md` — coaching chatbot spec
- `docs/schemas/db-schema.sql` — Supabase DDL
- `docs/schemas/db-patch-001.sql` — patch SQL for existing Supabase instances

---

## Design Principles

- UI labels: "stress escalation risk" — never "meltdown prediction"
- Person never sees raw `risk_score` — gentle actionable message only
- YAML rules always override ML in L2 (deterministic floor)
- WCAG 2.2 AA minimum — no saturated reds, no auto-sound
- L3 LLM prompts are air-gapped from all physiological data
