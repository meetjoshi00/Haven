"""L1 Phase 5 — ONNX export of two production models.

Produces:
  model_full.onnx             — 18 features (E4 + tablet/camera, controlled env)
  model_wearable.onnx         — 15 features (E4 wristband only)
  risk_calibration_wearable.json — wearable OOF calibration (full uses risk_calibration.json)

Training pipeline mirrors Phase 4 exactly:
  PerParticipantMedianImputer (per-participant fill on training data)
  -> SMOTE -> StandardScaler -> LogisticRegression

The ONNX inference imputer uses SimpleImputer(strategy="median") which is
equivalent to PerParticipantMedianImputer.transform_val() — global column medians.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import polars as pl
from imblearn.over_sampling import SMOTE
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_ROOT         = Path(__file__).parent.parent.parent
_FEATURES_DIR = _ROOT / "ml" / "data" / "features"
_MODELS_DIR   = _ROOT / "ml" / "models"

logger = logging.getLogger(__name__)


def _load_all_features() -> list[str]:
    """Return all 18 feature names from feature_schema.json (declaration order)."""
    schema = json.loads((_MODELS_DIR / "feature_schema.json").read_text())
    return [f["name"] for f in schema["features"]]


def _load_wearable_features() -> list[str]:
    """Return 15 wearable feature names (inference_excluded=false)."""
    schema = json.loads((_MODELS_DIR / "feature_schema.json").read_text())
    return [f["name"] for f in schema["features"] if not f["inference_excluded"]]


def _split_by_participants(
    fm: pl.DataFrame, feature_cols: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X_train, y_train, pids_train, ls_train, X_test, y_test).

    Splits on test_participants.json — 50 train / 7 blind test.
    ls_train = label_source column for train set (used by wearable OOF).
    """
    split = json.loads((_MODELS_DIR / "test_participants.json").read_text())
    test_set = {(p["participant_id"], p["condition"]) for p in split["test_participants"]}

    test_mask = fm.select(
        pl.struct(["participant_id", "condition"]).map_elements(
            lambda r: (r["participant_id"], r["condition"]) in test_set,
            return_dtype=pl.Boolean,
        )
    ).to_series()

    fm_train = fm.filter(~test_mask)
    fm_test  = fm.filter(test_mask)

    X_train  = fm_train.select(feature_cols).to_numpy(allow_copy=True).astype(float)
    y_train  = fm_train["label"].to_numpy().astype(int)
    pids_tr  = fm_train["participant_id"].to_numpy()
    ls_train = fm_train["label_source"].to_numpy()
    X_test   = fm_test.select(feature_cols).to_numpy(allow_copy=True).astype(float)
    y_test   = fm_test["label"].to_numpy().astype(int)
    return X_train, y_train, pids_tr, ls_train, X_test, y_test


def _train_with_smote(
    X: np.ndarray,
    y: np.ndarray,
    pids: np.ndarray,
) -> tuple[SimpleImputer, StandardScaler, LogisticRegression]:
    """Replicate Phase 4 training: PerParticipantMedianImputer -> SMOTE -> scaler -> LR.

    Returns inference-time components (SimpleImputer uses global medians, equivalent
    to PerParticipantMedianImputer.transform_val() used at Phase 4 blind test).
    """
    from ml.training.train import PerParticipantMedianImputer

    pp_imputer = PerParticipantMedianImputer().fit(X, pids)
    X_imp = pp_imputer.transform_train(X, pids)

    smote = SMOTE(sampling_strategy=1.0, random_state=42)
    X_smote, y_smote = smote.fit_resample(X_imp, y)
    X_smote = np.asarray(X_smote)
    y_smote = np.asarray(y_smote)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_smote)

    lr = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", random_state=42)
    lr.fit(X_scaled, y_smote)

    inference_imputer = SimpleImputer(strategy="median")
    inference_imputer.fit(X)

    return inference_imputer, scaler, lr


def _inference_proba(
    imputer: SimpleImputer,
    scaler: StandardScaler,
    lr: LogisticRegression,
    X: np.ndarray,
) -> np.ndarray:
    return lr.predict_proba(scaler.transform(imputer.transform(X)))[:, 1]


def _export_to_onnx(
    imputer: SimpleImputer,
    scaler: StandardScaler,
    lr: LogisticRegression,
    n_features: int,
    out_path: Path,
    X_all: np.ndarray,
) -> float:
    """Build Pipeline, convert to ONNX, parity check, write file. Returns max_delta."""
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from onnxruntime import InferenceSession

    pipe = Pipeline([("imputer", imputer), ("scaler", scaler), ("clf", lr)])

    onnx_model = convert_sklearn(
        pipe,
        initial_types=[("float_input", FloatTensorType([None, n_features]))],
        target_opset=17,
    )

    rng = np.random.default_rng(42)
    sample_idx = rng.choice(len(X_all), size=min(100, len(X_all)), replace=False)
    X_sample = X_all[sample_idx].copy()

    col_medians = np.nanmedian(X_sample, axis=0)
    nan_locs = np.isnan(X_sample)
    X_sample[nan_locs] = np.take(col_medians, np.where(nan_locs)[1])

    sklearn_proba = _inference_proba(imputer, scaler, lr, X_sample)

    session   = InferenceSession(onnx_model.SerializeToString())
    onnx_out  = session.run(None, {"float_input": X_sample.astype(np.float32)})
    proba_raw = onnx_out[1]
    onnx_proba = (
        proba_raw[:, 1] if isinstance(proba_raw, np.ndarray)
        else np.array([d[1] for d in proba_raw])
    )

    max_delta = float(np.max(np.abs(sklearn_proba - onnx_proba)))
    assert max_delta < 1e-4, f"ONNX parity check failed for {out_path.name}: max_delta={max_delta:.2e}"
    logger.info("ONNX parity check passed for %s: max_delta=%.2e", out_path.name, max_delta)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(onnx_model.SerializeToString())
    size_kb = out_path.stat().st_size // 1024
    logger.info("%s written: %s  (%d KB)", out_path.name, out_path, size_kb)

    return max_delta


def _wearable_oof_scores(
    X_train: np.ndarray,
    y_train: np.ndarray,
    pids_train: np.ndarray,
    ls_train: np.ndarray,
) -> np.ndarray:
    """Compute 5-fold OOF probabilities for wearable model, return label=1 & discrete scores.

    Mirrors Phase 4 StratifiedGroupKFold params (shuffle=True, seed=42).
    """
    from ml.training.train import PerParticipantMedianImputer

    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    oof_proba  = np.zeros(len(y_train), dtype=float)

    for train_idx, val_idx in sgkf.split(X_train, y_train, groups=pids_train):
        X_tr, y_tr = X_train[train_idx], y_train[train_idx]
        X_val       = X_train[val_idx]
        pids_tr     = pids_train[train_idx]

        pp_imp = PerParticipantMedianImputer().fit(X_tr, pids_tr)
        X_tr_imp  = pp_imp.transform_train(X_tr, pids_tr)
        X_val_imp = pp_imp.transform_val(X_val)

        smote = SMOTE(sampling_strategy=1.0, random_state=42)
        X_sm, y_sm = smote.fit_resample(X_tr_imp, y_tr)

        scaler = StandardScaler()
        X_sm_sc  = scaler.fit_transform(X_sm)
        X_val_sc = scaler.transform(X_val_imp)

        lr = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", random_state=42)
        lr.fit(X_sm_sc, y_sm)
        oof_proba[val_idx] = lr.predict_proba(X_val_sc)[:, 1]

    qualifying = (y_train == 1) & (ls_train == "discrete")
    return oof_proba[qualifying]


def export_onnx(config: dict) -> None:
    """Run Phase 5: produce model_full.onnx, model_wearable.onnx, risk_calibration_wearable.json."""
    from ml.training.calibrate_thresholds import calibrate_from_scores
    from ml.training.evaluate import compute_metrics

    all_features      = _load_all_features()       # 18
    wearable_features = _load_wearable_features()  # 15

    fm = pl.read_parquet(_FEATURES_DIR / "feature_matrix_v1.parquet")

    # ------------------------------------------------------------------
    # FULL MODEL — 18 features (controlled environment)
    # ------------------------------------------------------------------
    X_tr_full, y_tr_full, pids_tr_full, _, X_te_full, y_te_full = _split_by_participants(
        fm, all_features
    )
    logger.info(
        "Full model — train: %d windows | blind test (7 participants): %d windows",
        len(y_tr_full), len(y_te_full),
    )

    imp_full50, sc_full50, lr_full50 = _train_with_smote(X_tr_full, y_tr_full, pids_tr_full)
    full_metrics = compute_metrics(y_te_full, _inference_proba(imp_full50, sc_full50, lr_full50, X_te_full))
    full_auroc   = full_metrics["auroc"]
    full_f1      = full_metrics["f1"]
    logger.info("Full model blind test: AUROC=%.4f  F1=%.4f", full_auroc, full_f1)

    X_all_full  = fm.select(all_features).to_numpy(allow_copy=True).astype(float)
    y_all_full  = fm["label"].to_numpy().astype(int)
    pids_all    = fm["participant_id"].to_numpy()

    imp_full_all, sc_full_all, lr_full_all = _train_with_smote(X_all_full, y_all_full, pids_all)
    full_delta = _export_to_onnx(
        imp_full_all, sc_full_all, lr_full_all,
        len(all_features),
        _MODELS_DIR / "model_full.onnx",
        X_all_full,
    )

    # ------------------------------------------------------------------
    # WEARABLE MODEL — 15 features (E4 wristband only)
    # ------------------------------------------------------------------
    X_tr_wear, y_tr_wear, pids_tr_wear, ls_tr_wear, X_te_wear, y_te_wear = _split_by_participants(
        fm, wearable_features
    )
    logger.info(
        "Wearable model — train: %d windows | blind test: %d windows",
        len(y_tr_wear), len(y_te_wear),
    )

    wear_oof_scores = _wearable_oof_scores(X_tr_wear, y_tr_wear, pids_tr_wear, ls_tr_wear)
    calibrate_from_scores(
        wear_oof_scores, config,
        out_path=_MODELS_DIR / "risk_calibration_wearable.json",
    )

    imp_wear50, sc_wear50, lr_wear50 = _train_with_smote(X_tr_wear, y_tr_wear, pids_tr_wear)
    proba_te_wear = _inference_proba(imp_wear50, sc_wear50, lr_wear50, X_te_wear)
    wear_metrics  = compute_metrics(y_te_wear, proba_te_wear)
    wear_auroc    = wear_metrics["auroc"]
    wear_f1       = wear_metrics["f1"]
    logger.info("Wearable model blind test: AUROC=%.4f  F1=%.4f", wear_auroc, wear_f1)

    X_all_wear  = fm.select(wearable_features).to_numpy(allow_copy=True).astype(float)
    y_all_wear  = fm["label"].to_numpy().astype(int)

    imp_wear_all, sc_wear_all, lr_wear_all = _train_with_smote(X_all_wear, y_all_wear, pids_all)
    wear_delta = _export_to_onnx(
        imp_wear_all, sc_wear_all, lr_wear_all,
        len(wearable_features),
        _MODELS_DIR / "model_wearable.onnx",
        X_all_wear,
    )

    _print_milestone(
        full_auroc, full_f1, full_delta,
        wear_auroc, wear_f1, wear_delta,
        len(all_features), len(wearable_features),
    )


def _print_milestone(
    full_auroc: float, full_f1: float, full_delta: float,
    wear_auroc: float, wear_f1: float, wear_delta: float,
    n_full: int, n_wear: int,
) -> None:
    print("\n" + "=" * 60)
    print("PHASE 5 — ONNX EXPORT")
    print("=" * 60)
    print(f"\n  FULL MODEL (controlled env — E4 + tablet/camera)")
    print(f"    Features : {n_full}")
    print(f"    Blind test AUROC = {full_auroc:.4f}  F1 = {full_f1:.4f}")
    print(f"    ONNX parity (100 samples): max_delta={full_delta:.2e}  [PASS]")
    print(f"    -> ml/models/model_full.onnx")
    print(f"\n  WEARABLE MODEL (E4 wristband only)")
    print(f"    Features : {n_wear}")
    print(f"    Blind test AUROC = {wear_auroc:.4f}  F1 = {wear_f1:.4f}")
    print(f"    ONNX parity (100 samples): max_delta={wear_delta:.2e}  [PASS]")
    print(f"    -> ml/models/model_wearable.onnx")
    print(f"    -> ml/models/risk_calibration_wearable.json")
    print("\n" + "=" * 60)
