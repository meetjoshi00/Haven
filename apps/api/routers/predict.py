"""L1 Phase 6 — demo predict endpoints.

Two deployment modes:
  full     — model_full.onnx     (18 features: E4 + tablet/camera, controlled env)
  wearable — model_wearable.onnx (15 features: E4 wristband only)

Endpoints:
  POST /predict/scenario/start  — create in-memory demo session
  GET  /predict/stream/{id}     — SSE, one event per 5s, 20 ticks

ONNX models are gitignored. Generate with:
  python scripts/run_ml_pipeline.py --phase export
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator, Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_ROOT       = Path(__file__).parent.parent.parent.parent
_MODELS_DIR = _ROOT / "ml" / "models"

# ---------------------------------------------------------------------------
# Module-level singletons (lazy-loaded)
# ---------------------------------------------------------------------------

_models_loaded    = False
_models_available = False
_onnx_sessions: dict = {}   # "full" | "wearable" → InferenceSession
_coefs: dict        = {}   # "full" | "wearable" → {coef, scaler_mean, scaler_std, ...}
_feature_schema: list = [] # list of feature dicts from feature_schema.json
_sessions: dict     = {}   # demo_session_id → SessionState

_SESSION_TTL = timedelta(minutes=30)
_MAX_TICKS   = 20


def _load_models() -> None:
    global _models_loaded, _models_available
    if _models_loaded:
        return
    _models_loaded = True

    try:
        from onnxruntime import InferenceSession

        schema = json.loads((_MODELS_DIR / "feature_schema.json").read_text())
        _feature_schema.extend(schema["features"])

        for model_key, onnx_name, coef_name in [
            ("full",     "model_full.onnx",          "model_full_coef.json"),
            ("wearable", "model_wearable.onnx",       "model_wearable_coef.json"),
        ]:
            onnx_path = _MODELS_DIR / onnx_name
            coef_path = _MODELS_DIR / coef_name
            if not onnx_path.exists():
                logger.warning("L1 ONNX model not found: %s — run --phase export", onnx_path.name)
                return
            if not coef_path.exists():
                logger.warning("L1 coef file not found: %s — run --phase export", coef_path.name)
                return
            _onnx_sessions[model_key] = InferenceSession(str(onnx_path))
            _coefs[model_key] = json.loads(coef_path.read_text())

        _models_available = True
        logger.info(
            "L1 models loaded: full (%d feat) + wearable (%d feat)",
            _coefs["full"]["n_features"], _coefs["wearable"]["n_features"],
        )
    except Exception as exc:
        logger.warning("L1 model loading failed (%s) — /predict endpoints unavailable", exc)


def _require_models() -> None:
    _load_models()
    if not _models_available:
        raise HTTPException(
            503,
            detail=(
                "L1 ONNX models not available. "
                "Run: python scripts/run_ml_pipeline.py --phase export"
            ),
        )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    user_id:    str
    scenario:   Literal["calm", "escalating", "rapid_spike"]
    model_type: Literal["full", "wearable"]
    tick:       int      = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _clean_expired() -> None:
    now     = datetime.now(timezone.utc)
    expired = [sid for sid, s in _sessions.items() if now - s.started_at > _SESSION_TTL]
    for sid in expired:
        del _sessions[sid]


# ---------------------------------------------------------------------------
# Scenario feature generators
# ---------------------------------------------------------------------------

def _base_features(model_type: str, tick: int) -> dict:
    """Calm (low-stress) E4 readings in native dataset units.

    acc_svm is in Engagnition native units (~65/g). Resting = ~68.
    Motion artifact threshold = 150 (~2.3g). All values from training
    data distribution (scaler_mean / scaler_std as reference).
    """
    feats: dict = {
        "gsr_phasic_peak_count":           2.50,   # below training mean 6.68
        "gsr_phasic_peak_freq":            5.00,   # = peak_count * 2 (30s window)
        "gsr_tonic_mean":                  0.80,   # below mean 1.10 μS
        "gsr_tonic_slope":                 0.001,  # near zero
        "subject_norm_gsr_z":              1.50,   # above pop mean → suppresses risk (neg coef)
        "skin_temp_mean":                 32.00,   # near training mean 31.95°C
        "skin_temp_derivative":            0.001,  # near zero
        "subject_norm_st_z":               0.00,   # at population mean
        "acc_svm_mean":                   68.00,   # near resting (mean=69.82)
        "acc_svm_std":                    28.00,   # high variability → suppresses risk (neg coef)
        "acc_svm_max":                   150.00,   # near artifact threshold (mean=167.55)
        "acc_svm_above_threshold_ratio":   0.005,  # very few high-motion samples
        "condition_lpe":                   1,
        "condition_hpe":                   0,
        "session_elapsed_ratio":           tick / (_MAX_TICKS - 1),
    }
    if model_type == "full":
        feats["gaze_off_task_ratio"]      = 0.10   # near training mean 0.06 — mostly on-task
        feats["performance_failure_rate"] = 0.95   # near training mean 0.94
        feats["engagement_class_mode"]    = 2      # fully engaged
    return feats


def _generate_features(scenario: str, model_type: str, tick: int) -> dict:
    feats = _base_features(model_type, tick)

    if scenario == "calm":
        # Tiny deterministic variation around baseline — no trend
        noise = ((tick % 5) - 2) / 2          # -1 to +1, cycles
        feats["gsr_phasic_peak_count"] = max(1.0, 2.5 + noise * 0.5)
        feats["gsr_phasic_peak_freq"]  = max(2.0, 5.0 + noise * 1.0)
        feats["gsr_tonic_slope"]       = noise * 0.0005
        return feats

    if scenario == "escalating":
        # Calm for ticks 0-4; linear rise ticks 5-19.
        # acc_svm_std DECREASES (freeze pattern) and subject_norm_gsr_z DECREASES
        # — both drive risk up because their LR coefs are negative.
        progress = max(0.0, (tick - 4) / 15.0)
        feats["gsr_phasic_peak_count"]         = 2.50 + progress *  5.50   # → 8.0
        feats["gsr_phasic_peak_freq"]          = 5.00 + progress * 11.00   # → 16.0
        feats["gsr_tonic_mean"]                = 0.80 + progress *  1.00   # → 1.8
        feats["gsr_tonic_slope"]               = 0.001 + progress * 0.039  # → 0.04
        feats["subject_norm_gsr_z"]            = 1.50 + progress * (-2.00) # → -0.5
        feats["skin_temp_mean"]                = 32.00 + progress * (-0.50)# → 31.5
        feats["skin_temp_derivative"]          = 0.001 + progress * (-0.011)# → -0.01
        feats["subject_norm_st_z"]             = 0.00 + progress * (-0.50) # → -0.5
        feats["acc_svm_mean"]                  = 68.00 + progress * 12.00  # → 80.0
        feats["acc_svm_std"]                   = 28.00 + progress * (-16.00)# → 12.0
        feats["acc_svm_max"]                   = 150.00 + progress * 50.00 # → 200.0
        feats["acc_svm_above_threshold_ratio"] = 0.005 + progress * 0.045  # → 0.05
        if model_type == "full":
            feats["gaze_off_task_ratio"]       = 0.10 + progress * 0.10    # → 0.20
            feats["performance_failure_rate"]  = 0.95                       # stays near mean
            feats["engagement_class_mode"]     = round(max(0.0, 2.0 - progress * 1.0))
        return feats

    # rapid_spike: calm 0-4 → hard spike tick 5 → partial recovery 6-10 → elevated 11-19
    if tick < 5:
        spike = 0.0
    elif tick == 5:
        spike = 1.0
    elif tick <= 10:
        spike = 1.0 - (tick - 5) * 0.12   # 1.0 → 0.40
    else:
        spike = 0.40

    feats["gsr_phasic_peak_count"]         = 2.50 + spike *  8.50   # → 11.0 at spike
    feats["gsr_phasic_peak_freq"]          = 5.00 + spike * 17.00   # → 22.0
    feats["gsr_tonic_mean"]                = 0.80 + spike *  1.50   # → 2.3
    feats["gsr_tonic_slope"]               = 0.001 + spike * 0.089  # → 0.09
    feats["subject_norm_gsr_z"]            = 1.50 + spike * (-3.50) # → -2.0 at spike
    feats["skin_temp_mean"]                = 32.00 + spike * (-1.00)# → 31.0
    feats["skin_temp_derivative"]          = 0.001 + spike * (-0.026)# → -0.025
    feats["subject_norm_st_z"]             = 0.00 + spike * (-1.50) # → -1.5
    feats["acc_svm_mean"]                  = 68.00 + spike * 12.00  # → 80.0
    feats["acc_svm_std"]                   = 28.00 + spike * (-23.00)# → 5.0 at spike
    feats["acc_svm_max"]                   = 150.00 + spike * 50.00 # → 200.0
    feats["acc_svm_above_threshold_ratio"] = 0.005 + spike *  0.115 # → 0.12
    if model_type == "full":
        feats["gaze_off_task_ratio"]       = 0.10 + spike * 0.15    # → 0.25 at spike
        feats["performance_failure_rate"]  = 0.95
        feats["engagement_class_mode"]     = round(max(0.0, 2.0 - spike * 1.0))
    return feats


# ---------------------------------------------------------------------------
# SHAP → cause_tags mapping (mirrors feature_schema.json shap_cause_tag values)
# ---------------------------------------------------------------------------

_SHAP_TO_CAUSE: dict[str, str] = {
    "gsr_phasic_peak_count":         "internal_arousal",
    "gsr_phasic_peak_freq":          "sustained_stress",
    "gsr_tonic_slope":               "escalating_arousal",
    "acc_svm_mean":                  "motor_agitation",
    "acc_svm_above_threshold_ratio": "motor_agitation",
    "skin_temp_derivative":          "physiological_stress",
    "subject_norm_gsr_z":            "above_personal_baseline",
    "session_elapsed_ratio":         "fatigue_accumulation",
}


# ---------------------------------------------------------------------------
# ONNX inference + analytical SHAP
# ---------------------------------------------------------------------------

def _infer(
    model_type: str,
    features: dict,
) -> tuple[float, dict[str, float], list[str]]:
    """Run ONNX inference + LR analytical SHAP.

    Returns (risk_score, shap_values, cause_tags).
    shap_values contains top-2 features with non-null shap_cause_tag.
    cause_tags maps those features through _SHAP_TO_CAUSE (deduped, order-preserved).
    """
    coef_data   = _coefs[model_type]
    feat_names  = coef_data["feature_names"]
    coef        = np.array(coef_data["coef"],        dtype=float)
    scaler_mean = np.array(coef_data["scaler_mean"], dtype=float)
    scaler_std  = np.array(coef_data["scaler_std"],  dtype=float)

    # Build ordered feature vector (float32 for ONNX)
    x = np.array([float(features[n]) for n in feat_names], dtype=np.float32)

    # ONNX inference — pipeline handles imputation + scaling internally
    session  = _onnx_sessions[model_type]
    onnx_out = session.run(None, {"float_input": x.reshape(1, -1)})
    proba_raw = onnx_out[1]
    if isinstance(proba_raw, np.ndarray):
        risk_score = float(proba_raw[0, 1])
    else:
        risk_score = float(proba_raw[0][1])

    # Analytical LR SHAP: contribution_i = coef_i * (x_i - scaler_mean_i) / scaler_std_i
    x64      = x.astype(float)
    shap_all = coef * (x64 - scaler_mean) / scaler_std

    # Filter to features with a cause tag AND positive SHAP (risk-increasing only)
    tagged = [
        (i, name, shap_all[i])
        for i, name in enumerate(feat_names)
        if name in _SHAP_TO_CAUSE and shap_all[i] > 0
    ]
    tagged.sort(key=lambda t: abs(t[2]), reverse=True)
    top2 = tagged[:2]

    shap_values = {name: round(float(val), 4) for _, name, val in top2}
    # dict.fromkeys preserves insertion order and deduplicates cause tags
    cause_tags  = list(dict.fromkeys(_SHAP_TO_CAUSE[name] for _, name, _ in top2))

    return risk_score, shap_values, cause_tags


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class ScenarioStartRequest(BaseModel):
    user_id:    str
    scenario:   Literal["calm", "escalating", "rapid_spike"]
    model_type: Literal["full", "wearable"]


class ScenarioStartResponse(BaseModel):
    demo_session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scenario/start", response_model=ScenarioStartResponse)
async def scenario_start(body: ScenarioStartRequest):
    """Create a demo session. Returns demo_session_id for use with /stream/{id}."""
    _require_models()
    _clean_expired()

    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionState(
        user_id=body.user_id,
        scenario=body.scenario,
        model_type=body.model_type,
    )
    logger.info(
        "Demo session created: %s  scenario=%s  model=%s",
        session_id, body.scenario, body.model_type,
    )
    return ScenarioStartResponse(demo_session_id=session_id)


async def _sse_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Emit one SSE event per tick (5s interval). Sends {done: true} at end."""
    session = _sessions.get(session_id)
    if session is None:
        yield f"data: {json.dumps({'error': 'session not found or expired'})}\n\n"
        return

    try:
        while session.tick < _MAX_TICKS:
            features = _generate_features(session.scenario, session.model_type, session.tick)
            risk_score, shap_values, cause_tags = _infer(session.model_type, features)

            payload = {
                "risk_score":  round(risk_score, 4),
                "cause_tags":  cause_tags,
                "shap_values": shap_values,
                "features":    {k: round(float(v), 4) for k, v in features.items()},
                "ts":          datetime.now(timezone.utc).isoformat(),
                "user_id":     session.user_id,
                "model_type":  session.model_type,
                "demo":        True,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            session.tick += 1

            if session.tick < _MAX_TICKS:
                await asyncio.sleep(5)

        yield f"data: {json.dumps({'done': True})}\n\n"
    except asyncio.CancelledError:
        pass  # client disconnected cleanly
    finally:
        _sessions.pop(session_id, None)


@router.get("/stream/{demo_session_id}")
async def stream(demo_session_id: str):
    """SSE stream for a demo session. Emits L1→L2 contract payload every 5s."""
    _require_models()
    if demo_session_id not in _sessions:
        raise HTTPException(404, detail="Demo session not found or expired")

    return StreamingResponse(
        _sse_generator(demo_session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
