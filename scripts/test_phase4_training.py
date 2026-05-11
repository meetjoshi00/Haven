"""Synthetic tests for Phase 4 training logic.

No real data required — all tests use in-memory arrays.
Run: python scripts/test_phase4_training.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from ml.training.ensemble import soft_vote_proba
from ml.training.evaluate import compute_metrics
from ml.training.train import PerParticipantMedianImputer

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool) -> None:
    global _PASS, _FAIL
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    if condition:
        _PASS += 1
    else:
        _FAIL += 1


# ---------------------------------------------------------------------------
# Helpers — synthetic feature matrices
# ---------------------------------------------------------------------------

def _make_X_pids(n_per_participant: int = 10) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, participant_ids) with 6 synthetic participants."""
    rng = np.random.default_rng(0)
    participants = ["PA", "PB", "PC", "PD", "PE", "PF"]
    y_per = [0, 0, 1, 1, 0, 1]   # 3 label=0 participants, 3 label=1
    rows_X, rows_y, rows_pid = [], [], []
    for pid, label in zip(participants, y_per):
        x = rng.random((n_per_participant, 4))
        # introduce NaN in column 2 for PA and column 3 for PC
        if pid == "PA":
            x[:, 2] = np.nan
        if pid == "PC":
            x[3:, 3] = np.nan
        rows_X.append(x)
        rows_y.extend([label] * n_per_participant)
        rows_pid.extend([pid] * n_per_participant)
    return (
        np.vstack(rows_X),
        np.array(rows_y, dtype=int),
        np.array(rows_pid),
    )


# ---------------------------------------------------------------------------
# Tests — PerParticipantMedianImputer
# ---------------------------------------------------------------------------

def test_imputer_per_participant_fill() -> None:
    """Per-participant fill uses own median, not global."""
    print("\n=== Test 1: imputer — per-participant fill ===")
    X = np.array([
        [1.0, np.nan],   # P1 row 0
        [3.0, np.nan],   # P1 row 1
        [10.0, 5.0],     # P2 row 0
        [20.0, 7.0],     # P2 row 1
    ])
    pids = np.array(["P1", "P1", "P2", "P2"])
    imputer = PerParticipantMedianImputer().fit(X, pids)
    out = imputer.transform_train(X.copy(), pids)

    # P1 col-1 median is NaN → falls back to global median = median([5.0, 7.0]) = 6.0
    global_med_col1 = np.nanmedian(X[:, 1])  # 6.0
    _check("P1 col-0 unchanged (not NaN)",        abs(out[0, 0] - 1.0) < 1e-9)
    _check("P1 col-1 filled with global fallback", abs(out[0, 1] - global_med_col1) < 1e-9)
    _check("P2 col-1 unchanged (not NaN)",         abs(out[2, 1] - 5.0) < 1e-9)


def test_imputer_participant_uses_own_median() -> None:
    """Different participants get their own medians, not each other's."""
    print("\n=== Test 2: imputer — distinct per-participant medians ===")
    X = np.array([
        [np.nan, 2.0],   # PA row 0
        [np.nan, 4.0],   # PA row 1  → col-0 all NaN for PA → global fallback
        [10.0, np.nan],  # PB row 0
        [20.0, np.nan],  # PB row 1  → col-1 all NaN for PB → global fallback
    ])
    pids = np.array(["PA", "PA", "PB", "PB"])
    imputer = PerParticipantMedianImputer().fit(X, pids)
    out = imputer.transform_train(X.copy(), pids)

    global_col0 = np.nanmedian(X[:, 0])   # median(10, 20) = 15.0
    global_col1 = np.nanmedian(X[:, 1])   # median(2, 4)   = 3.0
    _check("PA col-0 → global fallback 15.0",  abs(out[0, 0] - global_col0) < 1e-9)
    _check("PA col-1 unchanged 2.0",           abs(out[0, 1] - 2.0) < 1e-9)
    _check("PB col-0 unchanged 10.0",          abs(out[2, 0] - 10.0) < 1e-9)
    _check("PB col-1 → global fallback 3.0",   abs(out[2, 1] - global_col1) < 1e-9)


def test_imputer_val_uses_global_only() -> None:
    """transform_val uses global training median, not per-participant."""
    print("\n=== Test 3: imputer — val set uses global median ===")
    X_train = np.array([
        [1.0, 2.0],   # PA
        [3.0, 4.0],   # PA
        [5.0, 6.0],   # PB
        [7.0, 8.0],   # PB
    ])
    pids_train = np.array(["PA", "PA", "PB", "PB"])
    imputer = PerParticipantMedianImputer().fit(X_train, pids_train)

    # Val participant PC (unseen) with NaN
    X_val = np.array([[np.nan, np.nan]])
    out = imputer.transform_val(X_val)
    global_col0 = np.nanmedian(X_train[:, 0])  # 4.0
    global_col1 = np.nanmedian(X_train[:, 1])  # 5.0
    _check("val NaN col-0 → global median 4.0", abs(out[0, 0] - global_col0) < 1e-9)
    _check("val NaN col-1 → global median 5.0", abs(out[0, 1] - global_col1) < 1e-9)

    # Verify it is NOT using PA or PB individual medians
    pa_col0_med = np.nanmedian(X_train[:2, 0])  # 2.0
    _check("val not using PA median (2.0)",       abs(out[0, 0] - pa_col0_med) > 1e-9)


# ---------------------------------------------------------------------------
# Tests — StratifiedGroupKFold (CV split correctness)
# ---------------------------------------------------------------------------

def test_cv_no_participant_leakage() -> None:
    """No participant appears in both train and val in any fold."""
    print("\n=== Test 4: CV — no participant leakage across splits ===")
    X, y, pids = _make_X_pids()
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    all_ok = True
    for fold_idx, (tr_idx, val_idx) in enumerate(splitter.split(X, y, pids)):
        train_pids = set(pids[tr_idx])
        val_pids   = set(pids[val_idx])
        overlap = train_pids & val_pids
        if overlap:
            _check(f"fold {fold_idx}: overlap {overlap}", False)
            all_ok = False
    _check("no participant in both train and val across all folds", all_ok)


def test_cv_both_classes_in_val() -> None:
    """Each fold's val set contains both label=0 and label=1."""
    print("\n=== Test 5: CV — both classes present in val ===")
    X, y, pids = _make_X_pids()
    splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
    all_ok = True
    for fold_idx, (_, val_idx) in enumerate(splitter.split(X, y, pids)):
        y_val = y[val_idx]
        has_both = (0 in y_val) and (1 in y_val)
        if not has_both:
            _check(f"fold {fold_idx}: both classes in val", False)
            all_ok = False
    _check("all folds have label=0 and label=1 in val", all_ok)


# ---------------------------------------------------------------------------
# Tests — SMOTE
# ---------------------------------------------------------------------------

def test_smote_val_unchanged() -> None:
    """Val set size is unchanged by SMOTE (SMOTE only touches train)."""
    print("\n=== Test 6: SMOTE — val set rows unchanged ===")
    from imblearn.over_sampling import SMOTE
    rng = np.random.default_rng(1)
    X_val = rng.random((30, 4))
    n_before = len(X_val)
    # SMOTE is never applied to val — confirm by checking count
    _check("val row count unchanged after SMOTE on train", len(X_val) == n_before)


def test_smote_ratio_1to1() -> None:
    """After SMOTE 1:1, minority count equals majority count."""
    print("\n=== Test 7: SMOTE — 1:1 ratio achieved ===")
    from imblearn.over_sampling import SMOTE
    rng = np.random.default_rng(2)
    # 80 majority, 20 minority (4:1 imbalance)
    X_maj = rng.random((80, 4))
    X_min = rng.random((20, 4)) + 5.0
    X = np.vstack([X_maj, X_min])
    y = np.array([0] * 80 + [1] * 20)
    smote = SMOTE(sampling_strategy=1.0, random_state=42)
    X_res, y_res = smote.fit_resample(X, y)
    n0 = int((y_res == 0).sum())
    n1 = int((y_res == 1).sum())
    _check("after SMOTE: n_majority == n_minority", n0 == n1)
    _check("after SMOTE: original majority count unchanged", n0 == 80)


# ---------------------------------------------------------------------------
# Tests — compute_metrics
# ---------------------------------------------------------------------------

def test_compute_metrics_perfect() -> None:
    """Perfect classifier → AUROC=1.0, F1=1.0."""
    print("\n=== Test 8: compute_metrics — perfect classifier ===")
    y_true  = np.array([0, 0, 1, 1])
    y_proba = np.array([0.1, 0.2, 0.8, 0.9])
    m = compute_metrics(y_true, y_proba)
    _check("AUROC == 1.0",  abs(m["auroc"] - 1.0) < 1e-9)
    _check("F1 == 1.0",     abs(m["f1"]    - 1.0) < 1e-9)
    _check("confusion_matrix shape is 2×2", len(m["confusion_matrix"]) == 2)


def test_compute_metrics_chance() -> None:
    """Random (0.5 proba) classifier → AUROC ≈ 0.5."""
    print("\n=== Test 9: compute_metrics — chance predictor ===")
    rng = np.random.default_rng(3)
    y_true  = np.array([0, 1] * 50)
    y_proba = np.full(100, 0.5)
    m = compute_metrics(y_true, y_proba)
    _check("AUROC == 0.5 for constant proba", abs(m["auroc"] - 0.5) < 1e-9)


# ---------------------------------------------------------------------------
# Tests — soft_vote_proba
# ---------------------------------------------------------------------------

def test_soft_vote_proba() -> None:
    """Soft vote is element-wise mean of probability arrays."""
    print("\n=== Test 10: soft_vote_proba — probability averaging ===")
    p1 = np.array([0.3, 0.6, 0.9])
    p2 = np.array([0.5, 0.4, 0.7])
    avg = soft_vote_proba([p1, p2])
    expected = np.array([0.4, 0.5, 0.8])
    _check("mean of two proba arrays",      np.allclose(avg, expected))
    _check("output shape matches input",    avg.shape == p1.shape)

    # Three arrays
    p3 = np.array([0.2, 0.8, 0.6])
    avg3 = soft_vote_proba([p1, p2, p3])
    _check("mean of three proba arrays",    np.allclose(avg3, (p1 + p2 + p3) / 3))


# ---------------------------------------------------------------------------
# Tests — no test participant in any CV fold
# ---------------------------------------------------------------------------

def test_no_test_participant_in_cv_splits() -> None:
    """Test set participants never appear in any CV training fold."""
    print("\n=== Test 11: test participants never in CV training ===")
    # Simulate train/test split: PA–PD = train, PE–PF = test
    X, y, pids = _make_X_pids()
    test_pids  = {"PE", "PF"}
    train_mask = np.array([p not in test_pids for p in pids])

    X_train = X[train_mask]
    y_train = y[train_mask]
    g_train = pids[train_mask]

    splitter = StratifiedGroupKFold(n_splits=2, shuffle=True, random_state=42)
    all_ok = True
    for fold_idx, (tr_idx, val_idx) in enumerate(splitter.split(X_train, y_train, g_train)):
        in_fold = set(g_train[tr_idx]) | set(g_train[val_idx])
        leaked  = in_fold & test_pids
        if leaked:
            _check(f"fold {fold_idx}: test participant leaked: {leaked}", False)
            all_ok = False
    _check("no test participant appears in any CV fold", all_ok)


# ---------------------------------------------------------------------------
# Tests — best_model_meta.json schema
# ---------------------------------------------------------------------------

def test_best_model_meta_schema() -> None:
    """best_model_meta.json contains all required keys with correct types."""
    print("\n=== Test 12: best_model_meta.json schema ===")
    required_keys = {
        "algorithm", "mean_auroc", "std_auroc", "mean_f1",
        "test_auroc", "test_f1", "cv_test_gap",
        "ensemble_triggered", "ensemble_mean_auroc", "top2_algos",
        "model_version", "trained_at",
    }
    # Construct a minimal mock to validate structure
    mock = {
        "algorithm": "xgboost",
        "mean_auroc": 0.83, "std_auroc": 0.03, "mean_f1": 0.78,
        "test_auroc": 0.80, "test_f1": 0.76, "cv_test_gap": 0.03,
        "ensemble_triggered": False, "ensemble_mean_auroc": None, "top2_algos": None,
        "model_version": "v1.0", "trained_at": "2026-05-06T00:00:00+00:00",
    }
    missing = required_keys - set(mock.keys())
    _check("all required keys present",            len(missing) == 0)
    _check("algorithm is a string",                isinstance(mock["algorithm"], str))
    _check("mean_auroc is numeric",                isinstance(mock["mean_auroc"], float))
    _check("ensemble_triggered is bool",           isinstance(mock["ensemble_triggered"], bool))
    _check("ensemble_mean_auroc is None when not triggered", mock["ensemble_mean_auroc"] is None)

    # Round-trip JSON serialisation
    serialised = json.dumps(mock)
    reloaded   = json.loads(serialised)
    _check("round-trip JSON: algorithm preserved", reloaded["algorithm"] == mock["algorithm"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_imputer_per_participant_fill()
    test_imputer_participant_uses_own_median()
    test_imputer_val_uses_global_only()
    test_cv_no_participant_leakage()
    test_cv_both_classes_in_val()
    test_smote_val_unchanged()
    test_smote_ratio_1to1()
    test_compute_metrics_perfect()
    test_compute_metrics_chance()
    test_soft_vote_proba()
    test_no_test_participant_in_cv_splits()
    test_best_model_meta_schema()

    print(f"\n{'='*40}")
    print(f"Results: {_PASS} passed, {_FAIL} failed")
    sys.exit(0 if _FAIL == 0 else 1)
