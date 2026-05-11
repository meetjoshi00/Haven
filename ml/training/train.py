"""L1 Phase 4 — multi-algorithm participant-stratified CV + blind test evaluation.

Flow:
  1. Load feature_matrix_v1.parquet
  2. Create (or load) participant train/test split — stored in ml/models/test_participants.json
  3. 5-fold StratifiedGroupKFold CV on training participants → select best algorithm
  4. If best mean AUROC < ensemble_auroc_threshold → run soft-voting ensemble (top-2)
  5. Retrain best algorithm on all training data → evaluate on blind test set
  6. Write ml/models/best_model_meta.json + ml/data/features/oof_predictions.parquet
"""
from __future__ import annotations

import json
import logging
import random
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
import sys

import mlflow
import numpy as np
import polars as pl
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from ml.adapters.engagnition_v1 import EngagnitionV1Adapter
from ml.training.ensemble import run_ensemble_cv
from ml.training.evaluate import compute_metrics

logger = logging.getLogger(__name__)

_RAW_DIR      = _ROOT / "ml" / "data" / "raw"
_FEATURES_DIR = _ROOT / "ml" / "data" / "features"
_MODELS_DIR   = _ROOT / "ml" / "models"
_MLFLOW_URI   = (_ROOT / "ml" / "experiments" / "mlruns").as_uri()

_ALL_FEATURE_COLS = [
    "gsr_phasic_peak_count", "gsr_phasic_peak_freq",
    "gsr_tonic_mean", "gsr_tonic_slope", "subject_norm_gsr_z",
    "skin_temp_mean", "skin_temp_derivative", "subject_norm_st_z",
    "acc_svm_mean", "acc_svm_std", "acc_svm_max", "acc_svm_above_threshold_ratio",
    "condition_lpe", "condition_hpe", "session_elapsed_ratio",
    "gaze_off_task_ratio", "performance_failure_rate", "engagement_class_mode",
]

_TEST_FRAC = 0.20


# ---------------------------------------------------------------------------
# Participant split
# ---------------------------------------------------------------------------

def _create_participant_split(config: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (train_pairs, test_pairs). Loads from disk if already created.

    Stratified 80/20 split of LPE/HPE participants by intervention_type.
    All baseline participants (P01–P19) always go to training.
    Writes ml/models/test_participants.json on first call (committed artifact).
    """
    split_path = _MODELS_DIR / "test_participants.json"

    if split_path.exists():
        data = json.loads(split_path.read_text())
        train_pairs = [(p["participant_id"], p["condition"]) for p in data["train_participants"]]
        test_pairs  = [(p["participant_id"], p["condition"]) for p in data["test_participants"]]
        logger.info("Loaded participant split: %d train, %d test", len(train_pairs), len(test_pairs))
        return train_pairs, test_pairs

    adapter    = EngagnitionV1Adapter(raw_dir=_RAW_DIR, config=config)
    lpe_pairs  = [(f"P{i:02d}", "LPE") for i in range(20, 39)]
    hpe_pairs  = [(f"P{i:02d}", "HPE") for i in range(39, 58)]

    by_itype: dict[str, list[tuple[str, str]]] = {"none": [], "discrete": [], "continuous": []}
    for pid, cond in lpe_pairs + hpe_pairs:
        _, intervention, _ = adapter.load(pid, cond)
        by_itype[intervention.intervention_type].append((pid, cond))

    rng       = random.Random(42)
    test_pairs: list[tuple[str, str]]  = []
    train_pairs: list[tuple[str, str]] = []

    for itype, pairs in by_itype.items():
        n_test = max(1, round(len(pairs) * _TEST_FRAC))
        shuffled = list(pairs)
        rng.shuffle(shuffled)
        test_pairs.extend(shuffled[:n_test])
        train_pairs.extend(shuffled[n_test:])

    baseline_pairs = [(f"P{i:02d}", "baseline") for i in range(1, 20)]
    train_pairs.extend(baseline_pairs)

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    split_path.write_text(json.dumps({
        "test_participants":  [{"participant_id": p, "condition": c} for p, c in test_pairs],
        "train_participants": [{"participant_id": p, "condition": c} for p, c in train_pairs],
        "split_strategy": "stratified_by_intervention_type",
        "random_state": 42,
    }, indent=2))
    logger.info("Created participant split: %d train, %d test -> %s", len(train_pairs), len(test_pairs), split_path)
    return train_pairs, test_pairs


# ---------------------------------------------------------------------------
# Imputer
# ---------------------------------------------------------------------------

class PerParticipantMedianImputer:
    """Impute NaN with per-participant column medians (training fold only).

    - fit(): computes per-participant and global medians from training fold.
    - transform_train(): fills each row using that participant's stored median;
      falls back to global median if that feature is all-null for the participant.
    - transform_val(): fills all NaN with global training median (val participants
      are held out — no per-participant stats available without leakage).
    """

    def fit(self, X: np.ndarray, participant_ids: np.ndarray) -> "PerParticipantMedianImputer":
        self._global_medians: np.ndarray = np.nanmedian(X, axis=0)
        # Replace any remaining NaN in global (all-null column) with 0
        self._global_medians = np.where(np.isnan(self._global_medians), 0.0, self._global_medians)

        self._participant_medians: dict[str, np.ndarray] = {}
        for pid in np.unique(participant_ids):
            mask = participant_ids == pid
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "All-NaN slice encountered")
                p_med = np.nanmedian(X[mask], axis=0)
            # Where participant has all-null for a feature, use global fallback
            p_med = np.where(np.isnan(p_med), self._global_medians, p_med)
            self._participant_medians[pid] = p_med
        return self

    def transform_train(self, X: np.ndarray, participant_ids: np.ndarray) -> np.ndarray:
        out = X.astype(float).copy()
        for i, pid in enumerate(participant_ids):
            nan_mask = np.isnan(out[i])
            if not nan_mask.any():
                continue
            fill = self._participant_medians.get(pid, self._global_medians)
            out[i] = np.where(nan_mask, fill, out[i])
        return out

    def transform_val(self, X: np.ndarray) -> np.ndarray:
        out = X.astype(float).copy()
        nan_mask = np.isnan(out)
        out = np.where(nan_mask, self._global_medians[np.newaxis, :], out)
        return out


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _build_model(algo: str):
    if algo == "logistic_regression":
        return LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", random_state=42)
    if algo == "random_forest":
        return RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    if algo == "xgboost":
        return XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            random_state=42, eval_metric="logloss", verbosity=0,
        )
    if algo == "lightgbm":
        return LGBMClassifier(
            n_estimators=200, learning_rate=0.1,
            random_state=42, verbose=-1,
        )
    raise ValueError(f"Unknown algorithm: {algo}")


# ---------------------------------------------------------------------------
# Single-fold runner
# ---------------------------------------------------------------------------

def _run_fold(
    algo: str,
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    pids_tr: np.ndarray,
    config: dict,
) -> dict:
    """Preprocess, fit, and evaluate one algorithm on one CV fold.

    Returns dict with auroc, f1, confusion_matrix, val_proba.
    val_proba is the raw class-1 probability array on the unmodified val set.
    """
    smote = SMOTE(sampling_strategy=1.0, random_state=42)

    if algo == "logistic_regression":
        imputer = PerParticipantMedianImputer().fit(X_tr, pids_tr)
        X_tr_imp  = imputer.transform_train(X_tr, pids_tr)
        X_val_imp = imputer.transform_val(X_val)
        X_tr_res, y_tr_res = smote.fit_resample(X_tr_imp, y_tr)
        X_tr_res = np.asarray(X_tr_res)
        scaler = StandardScaler()
        X_tr_final  = scaler.fit_transform(X_tr_res)
        X_val_final = scaler.transform(X_val_imp)
    else:
        global_med = np.where(np.isnan(np.nanmedian(X_tr, axis=0)), 0.0, np.nanmedian(X_tr, axis=0))
        X_tr_imp   = np.where(np.isnan(X_tr),  global_med[np.newaxis, :], X_tr)
        X_val_imp  = np.where(np.isnan(X_val), global_med[np.newaxis, :], X_val)
        X_tr_res, y_tr_res = smote.fit_resample(X_tr_imp, y_tr)
        X_tr_final  = np.asarray(X_tr_res)
        X_val_final = X_val_imp

    y_tr_res = np.asarray(y_tr_res)
    clf = _build_model(algo)
    clf.fit(X_tr_final, y_tr_res)
    val_proba = clf.predict_proba(X_val_final)[:, 1]
    metrics   = compute_metrics(y_val, val_proba)
    return {**metrics, "val_proba": val_proba}


# ---------------------------------------------------------------------------
# Test-set retrainer
# ---------------------------------------------------------------------------

def _retrain_and_evaluate_test(
    algo: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    groups_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    config: dict,
) -> dict:
    """Retrain best algorithm on all training data, evaluate on blind test set."""
    smote = SMOTE(sampling_strategy=1.0, random_state=42)

    if algo == "logistic_regression":
        imputer = PerParticipantMedianImputer().fit(X_train, groups_train)
        X_tr_imp   = imputer.transform_train(X_train, groups_train)
        X_test_imp = imputer.transform_val(X_test)
        X_tr_res, y_tr_res = smote.fit_resample(X_tr_imp, y_train)
        X_tr_res = np.asarray(X_tr_res)
        scaler = StandardScaler()
        X_tr_final   = scaler.fit_transform(X_tr_res)
        X_test_final = scaler.transform(X_test_imp)
    else:
        global_med   = np.where(np.isnan(np.nanmedian(X_train, axis=0)), 0.0, np.nanmedian(X_train, axis=0))
        X_tr_imp     = np.where(np.isnan(X_train), global_med[np.newaxis, :], X_train)
        X_test_imp   = np.where(np.isnan(X_test),  global_med[np.newaxis, :], X_test)
        X_tr_res, y_tr_res = smote.fit_resample(X_tr_imp, y_train)
        X_tr_final   = np.asarray(X_tr_res)
        X_test_final = X_test_imp

    y_tr_res = np.asarray(y_tr_res)

    clf = _build_model(algo)
    clf.fit(X_tr_final, y_tr_res)
    test_proba = clf.predict_proba(X_test_final)[:, 1]
    return compute_metrics(y_test, test_proba)


# ---------------------------------------------------------------------------
# Main CV orchestrator
# ---------------------------------------------------------------------------

def run_cv(config: dict) -> dict:
    """Full Phase 4 CV pipeline.

    Returns best_model_meta dict (also written to ml/models/best_model_meta.json).
    """
    mlflow.set_tracking_uri(_MLFLOW_URI)
    mlflow.set_experiment("L1-training")

    # --- Load feature matrix ---
    fm_path = _FEATURES_DIR / "feature_matrix_v1.parquet"
    fm = pl.read_parquet(fm_path)

    # --- Participant split ---
    train_pairs, test_pairs = _create_participant_split(config)
    train_set = {(p, c) for p, c in train_pairs}
    test_set  = {(p, c) for p, c in test_pairs}

    train_mask = fm.select(
        pl.struct(["participant_id", "condition"]).map_elements(
            lambda r: (r["participant_id"], r["condition"]) in train_set,
            return_dtype=pl.Boolean,
        )
    ).to_series()
    test_mask = ~train_mask

    fm_train = fm.filter(train_mask)
    fm_test  = fm.filter(test_mask)

    X_train  = fm_train.select(_ALL_FEATURE_COLS).to_numpy(allow_copy=True).astype(float)
    y_train  = fm_train["label"].to_numpy().astype(int)
    g_train  = fm_train["participant_id"].to_numpy()

    X_test   = fm_test.select(_ALL_FEATURE_COLS).to_numpy(allow_copy=True).astype(float)
    y_test   = fm_test["label"].to_numpy().astype(int)

    logger.info(
        "Train: %d windows (%d participants) | Test: %d windows (%d participants)",
        len(y_train), len(train_pairs), len(y_test), len(test_pairs),
    )

    # --- CV splits (precomputed — same splits reused for ensemble) ---
    n_folds  = int(config["cv_folds"])
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=42)
    splits   = list(splitter.split(X_train, y_train, g_train))

    # --- Per-algorithm CV ---
    algo_results: dict[str, dict] = {}
    oof_proba_by_algo: dict[str, np.ndarray] = {}

    for algo in ["logistic_regression", "random_forest", "xgboost", "lightgbm"]:
        fold_aurocs: list[float] = []
        fold_f1s:    list[float] = []
        cm_sum: list[list[int]] | None = None
        oof_proba = np.full(len(y_train), np.nan)

        with mlflow.start_run(run_name=algo):
            mlflow.set_tag("algorithm", algo)
            mlflow.set_tag("smote_ratio", "1:1")
            mlflow.log_param("n_folds",             n_folds)
            mlflow.log_param("n_train_participants", len(train_pairs))
            mlflow.log_param("n_test_participants",  len(test_pairs))
            mlflow.log_param("n_train_windows",      len(y_train))
            mlflow.log_param("n_features",           len(_ALL_FEATURE_COLS))

            for fold_idx, (tr_idx, val_idx) in enumerate(splits):
                result = _run_fold(
                    algo,
                    X_train[tr_idx], y_train[tr_idx],
                    X_train[val_idx], y_train[val_idx],
                    g_train[tr_idx],
                    config,
                )
                oof_proba[val_idx] = result["val_proba"]
                fold_aurocs.append(result["auroc"])
                fold_f1s.append(result["f1"])

                if cm_sum is None:
                    cm_sum = result["confusion_matrix"]
                else:
                    for r in range(2):
                        for c in range(2):
                            cm_sum[r][c] += result["confusion_matrix"][r][c]

                mlflow.log_metric(f"fold_{fold_idx}_auroc", result["auroc"], step=fold_idx)
                mlflow.log_metric(f"fold_{fold_idx}_f1",    result["f1"],    step=fold_idx)
                logger.info("  %s fold %d: AUROC=%.4f  F1=%.4f", algo, fold_idx, result["auroc"], result["f1"])

            mean_auroc = float(np.mean(fold_aurocs))
            std_auroc  = float(np.std(fold_aurocs))
            mean_f1    = float(np.mean(fold_f1s))

            mlflow.log_metric("mean_auroc", mean_auroc)
            mlflow.log_metric("std_auroc",  std_auroc)
            mlflow.log_metric("mean_f1",    mean_f1)

            with tempfile.TemporaryDirectory() as tmp:
                cm_path = Path(tmp) / "confusion_matrix.json"
                cm_path.write_text(json.dumps({"confusion_matrix": cm_sum}))
                mlflow.log_artifact(str(cm_path))

        algo_results[algo]      = {"mean_auroc": mean_auroc, "std_auroc": std_auroc, "mean_f1": mean_f1}
        oof_proba_by_algo[algo] = oof_proba
        logger.info("%s: mean_auroc=%.4f  std=%.4f  mean_f1=%.4f", algo, mean_auroc, std_auroc, mean_f1)

    # --- Select best algorithm ---
    best_algo    = max(algo_results, key=lambda a: algo_results[a]["mean_auroc"])
    best_cv_auroc = algo_results[best_algo]["mean_auroc"]

    logger.info("Best algorithm: %s  (mean_auroc=%.4f)", best_algo, best_cv_auroc)

    # --- Ensemble (if triggered) ---
    ensemble_triggered  = best_cv_auroc < float(config["ensemble_auroc_threshold"])
    ensemble_result     = None
    top2_algos: list[str] = []

    if ensemble_triggered:
        top2_algos = sorted(algo_results, key=lambda a: algo_results[a]["mean_auroc"], reverse=True)[:2]
        logger.info("Ensemble triggered (best AUROC %.4f < %.2f). Top-2: %s",
                    best_cv_auroc, config["ensemble_auroc_threshold"], top2_algos)
        ensemble_result = run_ensemble_cv(
            top2_algos=top2_algos,
            X_train=X_train,
            y_train=y_train,
            groups_train=g_train,
            splits=splits,
            fold_runner=_run_fold,
            config=config,
        )

    # --- Blind test evaluation ---
    test_metrics = _retrain_and_evaluate_test(
        best_algo, X_train, y_train, g_train, X_test, y_test, config,
    )
    cv_test_gap = best_cv_auroc - test_metrics["auroc"]

    with mlflow.start_run(run_name=f"{best_algo}_test_eval"):
        mlflow.set_tag("algorithm", best_algo)
        mlflow.set_tag("evaluation", "blind_test_set")
        mlflow.log_metric("test_auroc",   test_metrics["auroc"])
        mlflow.log_metric("test_f1",      test_metrics["f1"])
        mlflow.log_metric("cv_train_auroc", best_cv_auroc)
        mlflow.log_metric("cv_test_gap",  cv_test_gap)
        if cv_test_gap > 0.10:
            mlflow.set_tag("warning", "cv_test_gap > 0.10 — possible overfitting")

    logger.info(
        "Blind test  → AUROC=%.4f  F1=%.4f  (CV gap: %.4f%s)",
        test_metrics["auroc"], test_metrics["f1"], cv_test_gap,
        " — WARNING: gap > 0.10" if cv_test_gap > 0.10 else "",
    )

    # --- OOF predictions (for Phase 5 threshold calibration) ---
    best_oof = oof_proba_by_algo[best_algo]
    oof_df = fm_train.select(["participant_id", "condition", "window_start_s", "label", "label_source"]).with_columns(
        pl.Series("oof_risk_score", best_oof),
    )
    _FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    oof_path = _FEATURES_DIR / "oof_predictions.parquet"
    oof_df.write_parquet(oof_path)
    logger.info("OOF predictions written: %s", oof_path)

    # --- Write best_model_meta.json ---
    meta = {
        "algorithm":           best_algo,
        "mean_auroc":          best_cv_auroc,
        "std_auroc":           algo_results[best_algo]["std_auroc"],
        "mean_f1":             algo_results[best_algo]["mean_f1"],
        "test_auroc":          test_metrics["auroc"],
        "test_f1":             test_metrics["f1"],
        "cv_test_gap":         cv_test_gap,
        "ensemble_triggered":  ensemble_triggered,
        "ensemble_mean_auroc": ensemble_result["mean_auroc"] if ensemble_result else None,
        "top2_algos":          top2_algos if ensemble_triggered else None,
        "model_version":       config.get("model_version", "v1.0"),
        "trained_at":          datetime.now(timezone.utc).isoformat(),
    }
    meta_path = _MODELS_DIR / "best_model_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    logger.info("best_model_meta.json written: %s", meta_path)

    _print_milestone(algo_results, best_algo, test_metrics, ensemble_result, cv_test_gap)
    return meta


# ---------------------------------------------------------------------------
# Milestone summary
# ---------------------------------------------------------------------------

def _print_milestone(
    algo_results: dict,
    best_algo: str,
    test_metrics: dict,
    ensemble_result: dict | None,
    cv_test_gap: float,
) -> None:
    print("\n" + "=" * 65)
    print("PHASE 4 MILESTONE — CV + BLIND TEST RESULTS")
    print("=" * 65)
    print(f"\n{'Algorithm':<22} {'Mean AUROC':>12} {'Std':>8} {'Mean F1':>10}")
    print("-" * 54)
    for algo, res in sorted(algo_results.items(), key=lambda x: -x[1]["mean_auroc"]):
        marker = " *" if algo == best_algo else ""
        print(f"  {algo:<20} {res['mean_auroc']:>12.4f} {res['std_auroc']:>8.4f} {res['mean_f1']:>10.4f}{marker}")
    print()
    print(f"  Best (CV):  {best_algo}  mean_auroc={algo_results[best_algo]['mean_auroc']:.4f}")
    print(f"  Blind test: AUROC={test_metrics['auroc']:.4f}  F1={test_metrics['f1']:.4f}  gap={cv_test_gap:.4f}")
    if cv_test_gap > 0.10:
        print(f"  WARNING: CV-test gap {cv_test_gap:.4f} > 0.10 — check for overfitting")
    if ensemble_result:
        print(f"  Ensemble (soft-vote): mean_auroc={ensemble_result['mean_auroc']:.4f}")
    print("\n" + "=" * 65)
