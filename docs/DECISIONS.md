# Decisions & References

`[LOCKED]` = final, additive changes only.
`[CONFIRMED]` = settled for current build, revisable with justification.

---

## Cross-layer decisions

| Decision | Status | Rationale |
|---|---|---|
| Python 3.11.9 only | LOCKED | sentence-transformers + ONNX stable on 3.11, issues on 3.12+ |
| pathlib.Path everywhere | LOCKED | Windows path compat, no string concat bugs |
| L3 air-gapped from L1/L2 | LOCKED | Coaching LLM never references physiological state — user trust boundary |
| YAML rules override ML in L2 | LOCKED | Deterministic safety floor |
| All UI risk labels: "stress escalation risk" | LOCKED | Never "meltdown prediction" — overclaiming certainty harms caregivers |
| Person never sees raw risk_score | LOCKED | Showing a score causes anxiety; person gets gentle actionable message only |

---

## L3 decisions

| Decision | Status | Rationale |
|---|---|---|
| Session memory in Supabase Postgres | LOCKED | Cross-session SQL filtering; LangChain objects don't persist cleanly |
| Critic JSON additive-only | LOCKED | UI uses optional chaining — new fields never break clients |
| Distress check before intent classifier | LOCKED | Safety-critical ordering — no LLM latency before distress response |
| safe_response as full-page replace | LOCKED | No background content visible during distress |
| Content in Markdown + Git | LOCKED | Diffable, no vendor lock-in, LangChain reads only |
| Embedding model: all-MiniLM-L6-v2 | LOCKED | 384-dim, fast on CPU, adequate for scenario/memory similarity |

---

## L1 decisions

| Decision | Status | Rationale |
|---|---|---|
| Dataset: Engagnition only | LOCKED | QU Autism dropped — Engagnition confirmed as sole training source |
| Label: intervention-derived | LOCKED | Clinician-validated ground truth. Three types: discrete (timestamped), continuous (full session), none. Mixed actual + expert-judged potential interventions — both treated equally. |
| No cross-signal resampling | LOCKED | Each signal queried independently by time range. Window scalars computed at native sampling rates. No forward-fill across signals. |
| Baseline condition = normalisation reference | LOCKED | Per-subject GSR and ST z-score computed from baseline mean/std |
| Acc_SVM pre-computed | LOCKED | Use dataset's pre-computed SVM column. Do not recompute from X/Y/Z unless debugging. |
| SMOTE on feature vectors only | LOCKED | Never on raw signals |
| Participant-stratified CV | LOCKED | Entire participants held out per fold — no row-level random splits (prevents leakage) |
| Metrics: AUROC + F1 | LOCKED | Never raw accuracy on imbalanced classes |
| Export format: ONNX | LOCKED | Lightweight, cross-platform, CPU inference on Render |
| Window size, stride, lookahead | CONFIRMED | Hyperparameters. Examine data before fixing values. Starting points: window=30s, stride=5s, lookahead=60s. Test [15,30,60]s windows and [30,45,60,90]s lookahead. |
| Resampling values | CONFIRMED | Verify on actual data before finalising any threshold |
| Multi-algorithm Phase 1 | CONFIRMED | LR, RF, XGBoost, LightGBM compared. Best AUROC wins. Ensemble (soft voting top-2) if best < 0.80. |
| Training-only features | CONFIRMED | gaze_off_task_ratio, performance_failure_rate, engagement_class_mode used in training. Flagged inference_excluded=true in feature_schema.json. |
| risk_score_gte = data-derived Q25 | CONFIRMED | Computed from pre-intervention score distribution on validation set. Recalibrate after each retrain. Start at Q25 (catches 75% of events). Adjust based on false alarm rate. |
| Replay buffer on retrain | CONFIRMED | 70% new data + 30% stratified sample of old canonical Parquet. Ratio configurable. |

---

## L2 decisions

| Decision | Status | Rationale |
|---|---|---|
| False alarm stores full feature vector | LOCKED | risk_score, cause_tags, shap_values, all features at alert time — required for threshold recalibration |
| Person + emergency contact both notified | LOCKED | Caregiver not always present; real-world use requires self-notification |
| Person-facing language: gentle + actionable | LOCKED | Clinical language is inappropriate for self-directed alerts |
| Synthetic demo mode as first-class | CONFIRMED | No wearables available. Demo is not a workaround — it is the MVP. |
| Notification channels | CONFIRMED | In-app (Supabase Realtime) + SMS (Twilio) + email (Resend). Emergency contact notified on severity=high or user opt-in. |
| Cooldown per rule | CONFIRMED | Prevent alert fatigue. Demo mode: cooldown=0. |
| LLM narrative | CONFIRMED | Groq, 25 words max, generates "why" field only. Cached in Upstash Redis by cause_tags_hash. Static fallback if Groq fails. |

---

## Accessibility decisions

| Decision | Status | Rationale |
|---|---|---|
| WCAG 2.2 AA minimum | LOCKED | Legal baseline + ASD user needs |
| prefers-reduced-motion respected | LOCKED | Sensory sensitivity |
| Palette: off-white #F7F5F1, no saturated reds | LOCKED | Reduce visual overstimulation |
| No auto-sound | LOCKED | Auditory sensitivity |
| Literal button labels | LOCKED | Reduce ambiguity for autistic users |
| Atkinson Hyperlegible as preferred font | LOCKED | Low-vision readability, user-selectable |

---

## Clinical & dataset references

| Reference | Informs |
|---|---|
| Kim et al. (2024) DOI:10.1038/s41597-024-03132-3 | Engagnition dataset — L1 training data. N=57 ASD children, Empatica E4, GSR/ST/ACC, engagement/gaze/intervention annotations. [GitHub](https://github.com/dailyminiii/Engagnition) |
| Kleckner et al. (2018) | EDA motion artifact gating — L1 preprocessing |
| Imbiriba et al. (2024) PMC10739066 | AUROC 0.80 benchmark at 3-min lookahead — L1 reference target |
| Goodwin et al. (2019) DOI:10.1002/aur.2151 | Wearable biosensing methodology — L1 |
| Milton (2012) DOI:10.1080/09687599.2012.710008 | Rubric framing — L3 contextual awareness not NT mimicry |
| Laugeson & Frankel (2011) DOI:10.1007/s10803-011-1339-1 | PEERS skill taxonomy — L3 scenario design |
| Laugeson et al. (2014) DOI:10.1007/s10803-014-2108-8 | School-based PEERS — L3 workplace/school scenarios |
