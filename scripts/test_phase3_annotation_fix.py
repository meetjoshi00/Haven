"""Synthetic tests for Phase 3 feature extraction, label assignment, and window generation.

No real data required — builds in-memory DataFrames that mirror the canonical format.
Run: python scripts/test_phase3_annotation_fix.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from ml.features.extract import extract_features
from ml.features.label import assign_label
from ml.features.window import generate_windows
from ml.schema.canonical_v1 import InterventionRecord

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


_SCHEMA = {
    "sg_time_s":   pl.Float64,
    "gsr_us":      pl.Float64,
    "gsr_phasic":  pl.Float64,
    "gsr_tonic":   pl.Float64,
    "skin_temp_c": pl.Float64,
    "acc_svm":     pl.Float64,
    "engagement":  pl.Int32,
    "gaze":        pl.Int32,
    "performance": pl.Int32,
}


def _nulls(n: int, dtype: pl.DataType) -> pl.Series:
    return pl.Series([None] * n, dtype=dtype)


def _make_session_df() -> pl.DataFrame:
    """Synthetic canonical DataFrame: 4 separate signal-type row groups."""
    rng = np.random.default_rng(42)
    n_gsr, n_st, n_acc, n_ann, n_prf = 20, 20, 80, 60, 5

    gsr = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(0, 30, n_gsr).tolist(), dtype=pl.Float64),
        "gsr_us":      pl.Series(rng.uniform(0.5, 3.0, n_gsr).tolist(), dtype=pl.Float64),
        "gsr_phasic":  pl.Series(rng.uniform(0.0, 0.05, n_gsr).tolist(), dtype=pl.Float64),
        "gsr_tonic":   pl.Series(rng.uniform(0.8, 2.5, n_gsr).tolist(), dtype=pl.Float64),
        "skin_temp_c": _nulls(n_gsr, pl.Float64),
        "acc_svm":     _nulls(n_gsr, pl.Float64),
        "engagement":  _nulls(n_gsr, pl.Int32),
        "gaze":        _nulls(n_gsr, pl.Int32),
        "performance": _nulls(n_gsr, pl.Int32),
    })
    st = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(0, 30, n_st).tolist(), dtype=pl.Float64),
        "gsr_us":      _nulls(n_st, pl.Float64),
        "gsr_phasic":  _nulls(n_st, pl.Float64),
        "gsr_tonic":   _nulls(n_st, pl.Float64),
        "skin_temp_c": pl.Series(rng.uniform(30.0, 34.0, n_st).tolist(), dtype=pl.Float64),
        "acc_svm":     _nulls(n_st, pl.Float64),
        "engagement":  _nulls(n_st, pl.Int32),
        "gaze":        _nulls(n_st, pl.Int32),
        "performance": _nulls(n_st, pl.Int32),
    })
    acc = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(0, 30, n_acc).tolist(), dtype=pl.Float64),
        "gsr_us":      _nulls(n_acc, pl.Float64),
        "gsr_phasic":  _nulls(n_acc, pl.Float64),
        "gsr_tonic":   _nulls(n_acc, pl.Float64),
        "skin_temp_c": _nulls(n_acc, pl.Float64),
        "acc_svm":     pl.Series(rng.uniform(50, 120, n_acc).tolist(), dtype=pl.Float64),
        "engagement":  _nulls(n_acc, pl.Int32),
        "gaze":        _nulls(n_acc, pl.Int32),
        "performance": _nulls(n_acc, pl.Int32),
    })
    # Engagement rows — gaze/performance null in this row type
    eng = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(0, 30, n_ann).tolist(), dtype=pl.Float64),
        "gsr_us":      _nulls(n_ann, pl.Float64),
        "gsr_phasic":  _nulls(n_ann, pl.Float64),
        "gsr_tonic":   _nulls(n_ann, pl.Float64),
        "skin_temp_c": _nulls(n_ann, pl.Float64),
        "acc_svm":     _nulls(n_ann, pl.Float64),
        "engagement":  pl.Series(rng.integers(0, 3, n_ann).tolist(), dtype=pl.Int32),
        "gaze":        _nulls(n_ann, pl.Int32),
        "performance": _nulls(n_ann, pl.Int32),
    })
    # Gaze rows — engagement/performance null in this row type
    gaz = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(0, 30, n_ann).tolist(), dtype=pl.Float64),
        "gsr_us":      _nulls(n_ann, pl.Float64),
        "gsr_phasic":  _nulls(n_ann, pl.Float64),
        "gsr_tonic":   _nulls(n_ann, pl.Float64),
        "skin_temp_c": _nulls(n_ann, pl.Float64),
        "acc_svm":     _nulls(n_ann, pl.Float64),
        "engagement":  _nulls(n_ann, pl.Int32),
        "gaze":        pl.Series(rng.integers(0, 2, n_ann).tolist(), dtype=pl.Int32),
        "performance": _nulls(n_ann, pl.Int32),
    })
    # Performance rows — sparse event-based; 3 failures out of 5 -> rate = 0.6
    prf = pl.DataFrame({
        "sg_time_s":   pl.Series(np.linspace(2, 28, n_prf).tolist(), dtype=pl.Float64),
        "gsr_us":      _nulls(n_prf, pl.Float64),
        "gsr_phasic":  _nulls(n_prf, pl.Float64),
        "gsr_tonic":   _nulls(n_prf, pl.Float64),
        "skin_temp_c": _nulls(n_prf, pl.Float64),
        "acc_svm":     _nulls(n_prf, pl.Float64),
        "engagement":  _nulls(n_prf, pl.Int32),
        "gaze":        _nulls(n_prf, pl.Int32),
        "performance": pl.Series([1, 0, 1, 0, 1], dtype=pl.Int32),
    })

    return pl.concat([gsr, st, acc, eng, gaz, prf], how="vertical")


_CONFIG = {
    "window_size_s": 30, "stride_s": 10, "lookahead_s": 30,
    "eda_amplitude_min": 0.01, "acc_svm_artifact_threshold": 150,
}
_NORM = {"gsr_mean": 1.124, "gsr_std": 1.386, "st_mean": 31.74, "st_std": 1.807}
_META_LPE      = {"participant_id": "PTEST", "condition": "LPE",      "total_session_duration_s": 600.0}
_META_BASELINE = {"participant_id": "PTEST", "condition": "baseline",  "total_session_duration_s": None}


def test_annotation_fix() -> None:
    """Core fix: separate filters for each annotation signal type."""
    print("\n=== Test 1: annotation features — LPE participant ===")
    df = _make_session_df()
    f = extract_features((0.0, 30.0), df, _NORM, _META_LPE, _CONFIG)
    _check("gaze_off_task_ratio is not None",      f["gaze_off_task_ratio"] is not None)
    _check("performance_failure_rate is not None", f["performance_failure_rate"] is not None)
    _check("engagement_class_mode is not None",    f["engagement_class_mode"] is not None)
    _check("gaze_off_task_ratio in [0, 1]",        0.0 <= f["gaze_off_task_ratio"] <= 1.0)
    _check("performance_failure_rate == 0.6",      abs(f["performance_failure_rate"] - 0.6) < 1e-9)
    _check("engagement_class_mode in {0,1,2}",     f["engagement_class_mode"] in {0, 1, 2})


def test_baseline_annotation_null() -> None:
    """Baseline Parquets have no annotation columns at all (not just null rows)."""
    print("\n=== Test 2: annotation features — baseline participant (columns absent) ===")
    # Drop columns entirely, mirroring real baseline Parquets
    df_no_ann = _make_session_df().drop(["engagement", "gaze", "performance"])
    f = extract_features((0.0, 30.0), df_no_ann, _NORM, _META_BASELINE, _CONFIG)
    _check("gaze_off_task_ratio is None",      f["gaze_off_task_ratio"] is None)
    _check("performance_failure_rate is None", f["performance_failure_rate"] is None)
    _check("engagement_class_mode is None",    f["engagement_class_mode"] is None)
    _check("condition_lpe == 0",               f["condition_lpe"] == 0)
    _check("condition_hpe == 0",               f["condition_hpe"] == 0)
    _check("session_elapsed_ratio is None",    f["session_elapsed_ratio"] is None)


def test_contextual_features() -> None:
    """condition flags and session_elapsed_ratio."""
    print("\n=== Test 3: contextual features ===")
    df = _make_session_df()
    f_lpe = extract_features((0.0, 30.0), df, _NORM, _META_LPE, _CONFIG)
    _check("LPE: condition_lpe == 1",          f_lpe["condition_lpe"] == 1)
    _check("LPE: condition_hpe == 0",          f_lpe["condition_hpe"] == 0)
    _check("LPE: session_elapsed_ratio == 0",  f_lpe["session_elapsed_ratio"] == 0.0)

    meta_hpe = {"participant_id": "PTEST", "condition": "HPE", "total_session_duration_s": 600.0}
    f_hpe = extract_features((300.0, 330.0), df, _NORM, meta_hpe, _CONFIG)
    _check("HPE: condition_lpe == 0",          f_hpe["condition_lpe"] == 0)
    _check("HPE: condition_hpe == 1",          f_hpe["condition_hpe"] == 1)
    _check("HPE: session_elapsed_ratio == 0.5",abs(f_hpe["session_elapsed_ratio"] - 0.5) < 1e-9)


def test_null_gsr_window() -> None:
    """Fully null GSR in window -> peak counts = 0, tonic/z-score features = None."""
    print("\n=== Test 4: fully null GSR window ===")
    df_no_gsr = _make_session_df().filter(pl.col("gsr_us").is_null())
    f = extract_features((0.0, 30.0), df_no_gsr, _NORM, _META_LPE, _CONFIG)
    _check("gsr_phasic_peak_count == 0.0",  f["gsr_phasic_peak_count"] == 0.0)
    _check("gsr_phasic_peak_freq == 0.0",   f["gsr_phasic_peak_freq"] == 0.0)
    _check("gsr_tonic_mean is None",        f["gsr_tonic_mean"] is None)
    _check("gsr_tonic_slope is None",       f["gsr_tonic_slope"] is None)
    _check("subject_norm_gsr_z is None",    f["subject_norm_gsr_z"] is None)


def test_generate_windows() -> None:
    print("\n=== Test 5: generate_windows ===")
    wins = generate_windows(0.0, 100.0, 30.0, 10.0)
    _check("first window = (0.0, 30.0)",       wins[0] == (0.0, 30.0))
    _check("last window end <= 100.0",          wins[-1][1] <= 100.0)
    _check("stride 10s between starts",         abs(wins[1][0] - wins[0][0] - 10.0) < 1e-9)
    _check("all windows are 30s",               all(abs(w[1] - w[0] - 30.0) < 1e-9 for w in wins))
    _check("8 windows over 100s (0,10,...,70)", len(wins) == 8)
    _check("no window starting at 80 (80+30>100)", all(w[0] < 80.0 for w in wins))


def test_assign_label() -> None:
    print("\n=== Test 6: assign_label ===")
    iv_none = InterventionRecord(participant_id="P01", condition="baseline",
                                 intervention_type="none", discrete_timestamps_s=[])
    iv_cont = InterventionRecord(participant_id="P26", condition="LPE",
                                 intervention_type="continuous", discrete_timestamps_s=[])
    iv_disc = InterventionRecord(participant_id="P22", condition="LPE",
                                 intervention_type="discrete", discrete_timestamps_s=[35.0, 80.0])

    l, s = assign_label((0.0, 30.0), iv_none, 30.0, "none")
    _check("none -> (0, 'none')",                        l == 0 and s == "none")

    l, s = assign_label((0.0, 30.0), iv_cont, 30.0, "continuous")
    _check("continuous -> (1, 'continuous')",             l == 1 and s == "continuous")

    # ts=35 in [30, 60] -> label=1
    l, s = assign_label((0.0, 30.0), iv_disc, 30.0, "discrete")
    _check("discrete: ts=35 in lookahead [30,60] -> 1",  l == 1 and s == "discrete")

    # ts=80 in [60, 90] -> label=1
    l, s = assign_label((30.0, 60.0), iv_disc, 30.0, "discrete")
    _check("discrete: ts=80 in lookahead [60,90] -> 1",  l == 1 and s == "discrete")

    # no ts in [90, 120] -> label=0
    l, s = assign_label((60.0, 90.0), iv_disc, 30.0, "discrete")
    _check("discrete: no ts in [90,120] -> 0",           l == 0 and s == "discrete")

    # boundary: ts exactly at t_end -> label=1
    iv_boundary = InterventionRecord(participant_id="P22", condition="LPE",
                                     intervention_type="discrete", discrete_timestamps_s=[30.0])
    l, s = assign_label((0.0, 30.0), iv_boundary, 30.0, "discrete")
    _check("discrete: ts == t_end (boundary inclusive) -> 1", l == 1)


def test_mixed_schema_dataframe_build() -> None:
    """Simulate the pl.DataFrame(rows) build with baseline rows first (all None for
    annotation features) followed by LPE rows (float/int values). Without
    infer_schema_length=len(rows) Polars infers Null type and crashes on LPE values."""
    print("\n=== Test 7: mixed baseline+LPE rows DataFrame build ===")
    import polars as _pl

    # Simulate what run_phase3 produces: 3 baseline rows (None annotations) then 1 LPE row
    rows = [
        {"participant_id": "P01", "condition": "baseline", "label": 0,
         "gaze_off_task_ratio": None, "performance_failure_rate": None, "engagement_class_mode": None,
         "gsr_phasic_peak_count": 1.0},
        {"participant_id": "P02", "condition": "baseline", "label": 0,
         "gaze_off_task_ratio": None, "performance_failure_rate": None, "engagement_class_mode": None,
         "gsr_phasic_peak_count": 0.0},
        {"participant_id": "P22", "condition": "LPE", "label": 1,
         "gaze_off_task_ratio": 0.004329, "performance_failure_rate": 0.2, "engagement_class_mode": 1,
         "gsr_phasic_peak_count": 2.0},
    ]
    try:
        df = _pl.DataFrame(rows, infer_schema_length=len(rows))
        _check("DataFrame builds without error",             True)
        _check("gaze_off_task_ratio dtype is Float64",       df["gaze_off_task_ratio"].dtype == _pl.Float64)
        _check("engagement_class_mode dtype is not Null",    str(df["engagement_class_mode"].dtype) != "Null")
        _check("baseline row has null gaze_off_task_ratio",  df[0]["gaze_off_task_ratio"][0] is None)
        _check("LPE row has non-null gaze_off_task_ratio",   df[2]["gaze_off_task_ratio"][0] is not None)
    except Exception as e:
        _check(f"DataFrame build failed: {e}", False)


if __name__ == "__main__":
    test_annotation_fix()
    test_baseline_annotation_null()
    test_contextual_features()
    test_null_gsr_window()
    test_generate_windows()
    test_assign_label()
    test_mixed_schema_dataframe_build()

    print(f"\n{'='*40}")
    print(f"Results: {_PASS} passed, {_FAIL} failed")
    sys.exit(0 if _FAIL == 0 else 1)
