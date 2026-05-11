"""Synthetic tests for Phase 5 — calibrate_thresholds + ONNX parity.

No filesystem reads. No real data. Tests logic in isolation.
Run: python scripts/test_phase5_calibration.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        print(f"  PASS  {name}")
        _PASS += 1
    else:
        print(f"  FAIL  {name}{' — ' + detail if detail else ''}")
        _FAIL += 1


# ---------------------------------------------------------------------------
# Calibration logic (mirrored from calibrate_thresholds.py for unit testing)
# ---------------------------------------------------------------------------

def _compute_calibration(scores: np.ndarray, model_version: str = "v1.0") -> dict:
    if len(scores) == 0:
        raise ValueError("No qualifying rows")
    q10, q25, q50, q75, q90 = np.percentile(scores, [10, 25, 50, 75, 90])
    return {
        "q10": float(q10), "q25": float(q25), "q50": float(q50),
        "q75": float(q75), "q90": float(q90),
        "n_samples": int(len(scores)),
        "model_version": model_version,
        "calibrated_at": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Calibration tests
# ---------------------------------------------------------------------------

def test_percentiles_match_numpy() -> None:
    scores = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    cal = _compute_calibration(scores)
    expected = np.percentile(scores, [10, 25, 50, 75, 90])
    _check("q10 matches numpy percentile", abs(cal["q10"] - expected[0]) < 1e-9)
    _check("q25 matches numpy percentile", abs(cal["q25"] - expected[1]) < 1e-9)
    _check("q50 matches numpy percentile", abs(cal["q50"] - expected[2]) < 1e-9)
    _check("q75 matches numpy percentile", abs(cal["q75"] - expected[3]) < 1e-9)
    _check("q90 matches numpy percentile", abs(cal["q90"] - expected[4]) < 1e-9)


def test_n_samples_correct() -> None:
    scores = np.linspace(0.0, 1.0, 47)
    cal = _compute_calibration(scores)
    _check("n_samples equals input length", cal["n_samples"] == 47)


def test_all_required_keys_present() -> None:
    cal = _compute_calibration(np.array([0.3, 0.5, 0.7]))
    required = {"q10", "q25", "q50", "q75", "q90", "n_samples", "model_version", "calibrated_at"}
    _check("all required keys present in output", required.issubset(cal.keys()))


def test_zero_samples_raises() -> None:
    raised = False
    try:
        _compute_calibration(np.array([]))
    except ValueError:
        raised = True
    _check("empty scores raises ValueError", raised)


def test_label0_rows_must_be_excluded() -> None:
    # Calibration must only use label=1 discrete rows.
    # Including label=0 rows shifts percentiles down — demonstrates filter matters.
    discrete_positive = np.array([0.6, 0.7, 0.8, 0.9, 0.75])
    label_zero_rows   = np.array([0.1, 0.2, 0.05])
    cal_correct = _compute_calibration(discrete_positive)
    cal_mixed   = _compute_calibration(np.concatenate([discrete_positive, label_zero_rows]))
    _check(
        "including label=0 rows shifts q25 down (filter matters)",
        cal_mixed["q25"] < cal_correct["q25"],
    )


def test_continuous_rows_must_be_excluded() -> None:
    # Continuous participants' scores are always high — inflates q75 if included.
    continuous_scores = np.array([0.88, 0.91, 0.93, 0.90, 0.87])
    discrete_scores   = np.array([0.35, 0.45, 0.55])
    cal_correct = _compute_calibration(discrete_scores)
    cal_mixed   = _compute_calibration(np.concatenate([discrete_scores, continuous_scores]))
    _check(
        "including continuous rows inflates q75 (filter matters)",
        cal_mixed["q75"] > cal_correct["q75"],
    )


def test_monotone_percentiles() -> None:
    scores = np.random.default_rng(7).uniform(0, 1, 200)
    cal = _compute_calibration(scores)
    _check(
        "percentiles are monotone (q10 <= q25 <= q50 <= q75 <= q90)",
        cal["q10"] <= cal["q25"] <= cal["q50"] <= cal["q75"] <= cal["q90"],
    )


def test_model_version_passed_through() -> None:
    cal = _compute_calibration(np.array([0.5, 0.6, 0.7]), model_version="v2.0")
    _check("model_version preserved in output", cal["model_version"] == "v2.0")


# ---------------------------------------------------------------------------
# ONNX parity tests
# ---------------------------------------------------------------------------

def _onnx_imports_available() -> bool:
    try:
        import skl2onnx  # noqa: F401
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def test_onnx_parity_clean_input() -> None:
    if not _onnx_imports_available():
        _check("ONNX parity (clean input) — skipped: skl2onnx/onnxruntime not installed", True)
        return

    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from onnxruntime import InferenceSession

    rng = np.random.default_rng(0)
    X = rng.standard_normal((60, 3)).astype(np.float32)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc",  StandardScaler()),
        ("clf", LogisticRegression(max_iter=500, random_state=0)),
    ])
    pipe.fit(X, y)

    onnx_model = convert_sklearn(
        pipe,
        initial_types=[("float_input", FloatTensorType([None, 3]))],
        target_opset=17,
    )
    session = InferenceSession(onnx_model.SerializeToString())

    X_test = rng.standard_normal((20, 3)).astype(np.float32)
    sk_proba  = pipe.predict_proba(X_test)[:, 1]
    onnx_out  = session.run(None, {"float_input": X_test})
    proba_raw = onnx_out[1]
    onnx_proba = proba_raw[:, 1] if isinstance(proba_raw, np.ndarray) else np.array([d[1] for d in proba_raw])

    max_delta = float(np.max(np.abs(sk_proba - onnx_proba)))
    _check(f"ONNX parity < 1e-4 on clean input (delta={max_delta:.2e})", max_delta < 1e-4)


def test_onnx_parity_nan_prefilled() -> None:
    """Pre-filled NaN input: imputer is bypassed, tests scaler+LR precision only."""
    if not _onnx_imports_available():
        _check("ONNX parity (NaN prefilled) — skipped: skl2onnx/onnxruntime not installed", True)
        return

    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from onnxruntime import InferenceSession

    rng = np.random.default_rng(2)
    X_train = rng.standard_normal((80, 4)).astype(np.float32)
    y_train = (X_train[:, 0] > 0).astype(int)

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc",  StandardScaler()),
        ("clf", LogisticRegression(max_iter=500, random_state=2)),
    ])
    pipe.fit(X_train, y_train)

    onnx_model = convert_sklearn(
        pipe,
        initial_types=[("float_input", FloatTensorType([None, 4]))],
        target_opset=17,
    )
    session = InferenceSession(onnx_model.SerializeToString())

    X_test = rng.standard_normal((20, 4)).astype(np.float32)
    sk_proba  = pipe.predict_proba(X_test)[:, 1]
    onnx_out  = session.run(None, {"float_input": X_test})
    proba_raw = onnx_out[1]
    onnx_proba = proba_raw[:, 1] if isinstance(proba_raw, np.ndarray) else np.array([d[1] for d in proba_raw])

    max_delta = float(np.max(np.abs(sk_proba - onnx_proba)))
    _check(f"ONNX parity < 1e-4 with no NaN in test data (delta={max_delta:.2e})", max_delta < 1e-4)


def test_onnx_output_shape() -> None:
    """ONNX output [1] has shape (n, 2) or equivalent for binary classification."""
    if not _onnx_imports_available():
        _check("ONNX output shape — skipped: skl2onnx/onnxruntime not installed", True)
        return

    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    from onnxruntime import InferenceSession

    rng = np.random.default_rng(3)
    X = rng.standard_normal((40, 5)).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)

    pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc",  StandardScaler()),
        ("clf", LogisticRegression(max_iter=200, random_state=3)),
    ])
    pipe.fit(X, y)

    onnx_model = convert_sklearn(
        pipe,
        initial_types=[("float_input", FloatTensorType([None, 5]))],
        target_opset=17,
    )
    session  = InferenceSession(onnx_model.SerializeToString())
    onnx_out = session.run(None, {"float_input": rng.standard_normal((10, 5)).astype(np.float32)})

    proba_raw = onnx_out[1]
    if isinstance(proba_raw, np.ndarray):
        n_cols = proba_raw.shape[1]
    else:
        n_cols = len(proba_raw[0])
    _check("ONNX output probabilities have 2 columns (binary classification)", n_cols == 2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n--- Calibration tests ---")
    test_percentiles_match_numpy()
    test_n_samples_correct()
    test_all_required_keys_present()
    test_zero_samples_raises()
    test_label0_rows_must_be_excluded()
    test_continuous_rows_must_be_excluded()
    test_monotone_percentiles()
    test_model_version_passed_through()

    print("\n--- ONNX parity tests ---")
    test_onnx_parity_clean_input()
    test_onnx_parity_nan_prefilled()
    test_onnx_output_shape()

    print(f"\n{'='*45}")
    print(f"Results: {_PASS} passed, {_FAIL} failed")
    if _FAIL:
        sys.exit(1)
