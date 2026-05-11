"""Evaluation metrics for L1 Phase 4 training."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score


def compute_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.5,
) -> dict:
    """Return AUROC, F1, and confusion matrix for one fold or test set.

    Args:
        y_true: Binary labels (0/1).
        y_pred_proba: Class-1 probabilities from predict_proba()[:, 1].
        threshold: Decision threshold for binary predictions (default 0.5).

    Returns:
        {"auroc": float, "f1": float, "confusion_matrix": [[tn, fp], [fn, tp]]}
    """
    y_pred = (y_pred_proba >= threshold).astype(int)
    auroc = float(roc_auc_score(y_true, y_pred_proba))
    f1    = float(f1_score(y_true, y_pred, zero_division=0))
    cm    = confusion_matrix(y_true, y_pred).tolist()
    return {"auroc": auroc, "f1": f1, "confusion_matrix": cm}
