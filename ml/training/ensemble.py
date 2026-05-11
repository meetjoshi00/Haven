"""Soft-voting ensemble for L1 Phase 4.

Triggered when best single-model CV mean AUROC < ensemble_auroc_threshold.
Uses the same precomputed fold splits as the main CV loop — no data leakage.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Callable

import mlflow
import numpy as np

from ml.training.evaluate import compute_metrics

logger = logging.getLogger(__name__)


def soft_vote_proba(probas: list[np.ndarray]) -> np.ndarray:
    """Element-wise mean of class-1 probability arrays from top-2 models."""
    return np.mean(np.stack(probas, axis=0), axis=0)


def run_ensemble_cv(
    top2_algos: list[str],
    X_train: np.ndarray,
    y_train: np.ndarray,
    groups_train: np.ndarray,
    splits: list[tuple[np.ndarray, np.ndarray]],
    fold_runner: Callable,
    config: dict,
) -> dict:
    """Run soft-voting CV for top-2 algorithms and log to MLflow.

    Refits each algorithm per fold (does not reuse Phase 4 fitted models).
    Uses the same splits list as the main CV loop — identical fold boundaries.

    Returns:
        {"mean_auroc": float, "std_auroc": float, "mean_f1": float}
    """
    fold_aurocs: list[float] = []
    fold_f1s: list[float] = []
    cm_sum: list[list[int]] | None = None

    with mlflow.start_run(run_name="ensemble_top2"):
        mlflow.set_tag("algorithm", "ensemble_soft_vote")
        mlflow.set_tag("component_algos", ",".join(top2_algos))
        mlflow.set_tag("smote_ratio", "1:1")

        for fold_idx, (tr_idx, val_idx) in enumerate(splits):
            X_fold_tr  = X_train[tr_idx]
            y_fold_tr  = y_train[tr_idx]
            X_fold_val = X_train[val_idx]
            y_fold_val = y_train[val_idx]
            pids_tr    = groups_train[tr_idx]

            probas: list[np.ndarray] = []
            for algo in top2_algos:
                result = fold_runner(algo, X_fold_tr, y_fold_tr, X_fold_val, y_fold_val, pids_tr, config)
                probas.append(result["val_proba"])

            avg_proba = soft_vote_proba(probas)
            metrics   = compute_metrics(y_fold_val, avg_proba)

            fold_aurocs.append(metrics["auroc"])
            fold_f1s.append(metrics["f1"])

            if cm_sum is None:
                cm_sum = metrics["confusion_matrix"]
            else:
                for r in range(2):
                    for c in range(2):
                        cm_sum[r][c] += metrics["confusion_matrix"][r][c]

            mlflow.log_metric(f"fold_{fold_idx}_auroc", metrics["auroc"], step=fold_idx)
            mlflow.log_metric(f"fold_{fold_idx}_f1",    metrics["f1"],    step=fold_idx)

        mean_auroc = float(np.mean(fold_aurocs))
        std_auroc  = float(np.std(fold_aurocs))
        mean_f1    = float(np.mean(fold_f1s))

        mlflow.log_metric("mean_auroc", mean_auroc)
        mlflow.log_metric("std_auroc",  std_auroc)
        mlflow.log_metric("mean_f1",    mean_f1)

        with tempfile.TemporaryDirectory() as tmp:
            import json
            cm_path = Path(tmp) / "ensemble_confusion_matrix.json"
            cm_path.write_text(json.dumps({"confusion_matrix": cm_sum}))
            mlflow.log_artifact(str(cm_path))

    logger.info(
        "Ensemble (%s): mean_auroc=%.4f  std=%.4f  mean_f1=%.4f",
        "+".join(top2_algos), mean_auroc, std_auroc, mean_f1,
    )
    return {"mean_auroc": mean_auroc, "std_auroc": std_auroc, "mean_f1": mean_f1}
