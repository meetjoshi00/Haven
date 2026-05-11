# L1 — Stress Escalation Predictor

## Status: Ready to build (Session 6–7)

---

## Dataset

**Engagnition** (Kim et al. 2024 — DOI:10.1038/s41597-024-03132-3)
- N=57 ASD children, Empatica E4 wristband
- Conditions: Baseline (rest, no game), LPE (low physical exertion), HPE (high physical exertion)
- Signals: GSR/EDA (4Hz), Skin Temperature (4Hz), ACC X/Y/Z/SVM (32Hz)
- Annotations (LPE + HPE only): Engagement (60Hz, 0/1/2), Gaze fixation (60Hz, 0/1), Intervention (event-based)
- Raw data location: `ml/data/raw/` (gitignored)

**Conditions:**
- Baseline → physiology only, no annotations → used for per-subject normalisation reference
- LPE + HPE → physiology + annotations → training data

---

## Pipeline overview

```
ml/data/raw/          (Engagnition CSVs)
    ↓ engagnition_v1.py adapter
ml/data/canonical/    (per-participant Parquet, native rates, no resampling)
    ↓ preprocessing
    ↓ feature extraction (window-based scalars, signals queried independently)
    ↓ label construction (intervention-derived)
ml/data/features/     feature_matrix_v1.parquet
    ↓ multi-algo training + participant-stratified CV
    ↓ best model → ONNX
ml/models/            model.onnx + feature_schema.json + risk_calibration.json
```

---

## Adapter pattern

`ml/adapters/base_adapter.py` — abstract base class. All future dataset adapters extend this.

`ml/adapters/engagnition_v1.py` — reads Engagnition CSVs, outputs canonical Parquet.

Each signal file (E4GsrData, E4TmpData, E4AccData, GazeData, EngagementData, PerformanceData) is read independently at its native timestamps. Signals are NOT merged or resampled at ingestion. Canonical Parquet stores each signal in its own columns with its own SGTime values.

InterventionData.xlsx (global file) → parsed separately → stored as `InterventionTimestamp` records alongside canonical Parquet.

Future dataset: write a new adapter. Training code unchanged.

---

## Canonical schema v1.0

```python
# ml/schema/canonical_v1.py
participant_id: str          # "P20"
source_dataset: str          # "engagnition_v1"
schema_version: str          # "1.0"
condition: str               # "baseline" | "LPE" | "HPE"
sg_time_s: float             # session-relative seconds (native to each signal)
unix_time: int               # Unix epoch int64
gsr_us: float | None         # μS, 4Hz native. Null if artifact-gated.
skin_temp_c: float | None    # °C, 4Hz native
acc_x: float | None          # g, 32Hz native
acc_y: float | None
acc_z: float | None
acc_svm: float | None        # pre-computed in dataset, 32Hz
engagement: int | None       # 0/1/2, 60Hz. Null for baseline.
gaze: int | None             # 0/1, 60Hz. Null for baseline.
performance: int | None      # 0/1, event-based. Null for baseline.
intervention_type: str | None  # "none" | "discrete" | "continuous". Null for baseline.
age: int
diagnosis: str               # "ASD" | "ASD,ID" | "ADHD"
nasa_tlx_weighted: float | None
sus_score: float | None
```

Discrete intervention timestamps stored in a companion lookup table (not per-row).

---

## Preprocessing

**Step 1 — Subject normalisation**
Load each participant's baseline Parquet. Compute `baseline_gsr_mean`, `baseline_gsr_std`, `baseline_st_mean`, `baseline_st_std`. Save to `ml/models/normalisation/{participant_id}.json`. Used during feature extraction to produce subject_norm_z features.

**Step 2 — Motion artifact gating (Kleckner 2018)**
Flag GSR windows where ACC_SVM exceeds a motion threshold. Threshold: examine data distribution before fixing. Flagged windows: `gsr_us = null`. Do not drop windows — missing values handled by model.

**Step 3 — EDA decomposition (NeuroKit2)**
Method: cvxEDA. Input: gsr_us series (4Hz, artifact-gated). Output: phasic component (SCR peaks) + tonic component (SCL baseline). Verify decomposition quality on one sample participant before batch processing.

---

## Feature extraction

For each window `[t_start, t_end]`, each signal queried independently by time range. No cross-signal resampling. No forward-fill.

```
# GSR features  (from gsr_df where SGTime in [t_start, t_end])
gsr_phasic_peak_count       — number of SCR peaks
gsr_phasic_peak_freq        — peaks per minute
gsr_tonic_mean              — mean tonic level
gsr_tonic_slope             — linear slope (positive = rising)
subject_norm_gsr_z          — z-score vs this subject's baseline

# ST features  (from tmp_df where SGTime in [t_start, t_end])
skin_temp_mean
skin_temp_derivative        — rate of change (negative = dropping)
subject_norm_st_z

# ACC features  (from acc_df at 32Hz native, within [t_start, t_end])
acc_svm_mean
acc_svm_std
acc_svm_max
acc_svm_above_threshold_ratio   — examine data to set threshold

# Contextual (available at inference)
condition_lpe               — bool
condition_hpe               — bool
session_elapsed_ratio       — t_start / total_session_duration

# Training-only (inference_excluded=true in feature_schema.json)
gaze_off_task_ratio         — mean(gaze==0) within window
performance_failure_rate    — failures/total_actions within window
engagement_class_mode       — mode of engagement within window
```

Window parameters — hyperparameters, test before fixing:
- Window size: test [15, 30, 60] seconds
- Stride: test [5, 10] seconds
- Lookahead: test [30, 45, 60, 90] seconds

---

## Label construction

```
intervention_type = "none"       → label=0 for all windows in session
intervention_type = "continuous" → label=1 for all windows in session
intervention_type = "discrete"   →
    label=1 if any discrete_timestamp falls in [t_end, t_end + LOOKAHEAD_S]
    label=0 otherwise

label_source stored alongside: "discrete" | "continuous" | "none"
(for diagnostics and threshold calibration — not used as training signal)
```

Note: InterventionData contains both actual interventions and expert-judged potential interventions. Both treated equally as clinician-validated ground truth.

---

## Training

**Phase 1 — Compare all algorithms**
Models: LogisticRegression, RandomForest, XGBoost, LightGBM
CV: participant-stratified 5-fold (entire participants held out, never row-level splits)
Imbalance: SMOTE applied to training fold only, never validation fold
Metrics: AUROC (primary), F1 (secondary)
Tracking: MLflow local (`ml/experiments/mlruns/`)
Selection: highest mean AUROC across folds

**Phase 2 — Ensemble (if best Phase 1 AUROC < 0.80)**
Soft voting, top-2 models from Phase 1.

**Phase 3 — Final model**
Retrain winner on all participants. Export to ONNX.

**Future data / replay buffer**
On retrain: 70% new data + 30% stratified sample of old canonical Parquet. Ratio configurable. Old Parquet never deleted.

---

## Threshold calibration

After training, on held-out validation participants:
1. Collect `risk_score` for all windows where `label=1` AND `label_source="discrete"`
2. Compute percentile distribution
3. Write to `ml/models/risk_calibration.json`:

```json
{
  "q10": 0.0, "q25": 0.0, "q50": 0.0, "q75": 0.0, "q90": 0.0,
  "n_samples": 0,
  "model_version": "v1.0",
  "calibrated_at": ""
}
```

L2 YAML reads `q25` as default `risk_score_gte`. Recalibrate after every retrain. Adjust based on false alarm rate post-deployment.

---

## SHAP cause tag mapping

```python
SHAP_TO_CAUSE = {
    "gsr_phasic_peak_count":          "internal_arousal",
    "gsr_phasic_peak_freq":           "sustained_stress",
    "gsr_tonic_slope":                "escalating_arousal",
    "acc_svm_mean":                   "motor_agitation",
    "acc_svm_above_threshold_ratio":  "motor_agitation",
    "skin_temp_derivative":           "physiological_stress",
    "subject_norm_gsr_z":             "above_personal_baseline",
    "session_elapsed_ratio":          "fatigue_accumulation",
    # Training-only (excluded from inference SHAP output):
    "gaze_off_task_ratio":            "attention_disengagement",
    "performance_failure_rate":       "task_overwhelm",
}
# Top-2 SHAP contributors by absolute value → cause_tags[]
```

---

## Output contract → L2

```json
{
  "risk_score": 0.73,
  "cause_tags": ["internal_arousal", "motor_agitation"],
  "shap_values": {"gsr_phasic_peak_count": 0.34, "acc_svm_mean": 0.28},
  "features": {},
  "ts": "2026-05-04T14:35:00Z",
  "user_id": "uuid",
  "demo": false
}
```

---

## API endpoints

```
POST /predict/scenario/start
     body: {user_id, scenario: "calm"|"escalating"|"rapid_spike"}
     returns: {demo_session_id}

GET  /predict/stream/{demo_session_id}
     Server-Sent Events, emits every 5s
     returns: {risk_score, cause_tags, ts, scenario_t}
```

Real wearable inference: add device adapters when hardware available. `source` field in signal ingest distinguishes `demo_synthetic` from `empatica_e4` or future devices.

---

## Files to produce

```
ml/
├── adapters/base_adapter.py
├── adapters/engagnition_v1.py
├── schema/canonical_v1.py
├── preprocessing/normalise.py
├── preprocessing/artifact_gate.py
├── preprocessing/eda_decompose.py
├── features/window.py
├── features/extract.py
├── features/label.py
├── training/train.py
├── training/evaluate.py
├── training/ensemble.py
├── training/calibrate_thresholds.py
├── export/to_onnx.py
└── models/feature_schema.json   (committed — everything else gitignored)
scripts/run_ml_pipeline.py
```

```

## Implementation notes

```
### InterventionData timestamp alignment
Timestamps in `InterventionData.xlsx` are session-relative seconds
in the same SGTime reference frame as all signal CSVs. Direct
comparison — no offset calculation needed.

### ST irregular timestamps
E4TmpData timestamps are slightly irregular (~4Hz, not perfectly
spaced). During feature extraction, filter rows by SGTime within
window bounds. Compute mean directly on available readings.
For derivative, use `numpy.polyfit(sg_times, st_values, deg=1)`
slope coefficient — handles irregular spacing correctly. Do not
interpolate to a regular grid.

### NeuroKit2 peak detection
Decomposition: cvxEDA. Peak detection: `eda_peaks` with
`amplitude_min=0.01` μS (half the NeuroKit2 default of 0.02 —
adjusted for ASD children whose GSR amplitude is typically lower).
Visually inspect peaks on 3 participants before running full
pipeline. Final value stored in `ml/config.yaml`.

### Motion artifact threshold
Do not hardcode. Inspect ACC_SVM distribution across all
participants in LPE and HPE (mean, std, 90th percentile) before
writing `artifact_gate.py`. Store final value in `ml/config.yaml`.

### Window, stride, lookahead
Do not hardcode. Before writing `window.py`, inspect: average
session duration per condition, average number of discrete
intervention timestamps per participant, distribution of time gaps
between consecutive interventions. Store final values in
`ml/config.yaml`.

### Null feature handling
XGBoost and LightGBM handle NaN natively — pass through as-is.
LogisticRegression: impute with participant's session median (not
global median). Implement as a Pydantic-validated step.

### Feature scaling
Apply StandardScaler before LogisticRegression only. Tree models
(XGBoost, LightGBM, RandomForest) receive raw features. Scalers
are separate pipeline steps so ONNX export captures the full
transform chain.

### Parquet partitioning
Hive-style: `ml/data/canonical/condition={condition}/
participant={participant_id}/data.parquet`
Queryable by Polars without loading all files.

### Pipeline tracking
Plain scripts + MLflow only. DVC added when second dataset arrives.

### config.yaml
All hyperparameters and data-derived thresholds live here.
Never hardcode values that depend on data inspection.
