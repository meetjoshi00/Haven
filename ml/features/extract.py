from __future__ import annotations

import numpy as np
import polars as pl
from scipy.signal import find_peaks


def extract_features(
    window: tuple[float, float],
    dfs: pl.DataFrame,
    norm_stats: dict,
    meta: dict,
    config: dict,
) -> dict:
    """Extract 18 features from one window of a preprocessed session DataFrame.

    dfs: full session preprocessed Parquet (gsr_phasic + gsr_tonic columns present).
    Returns a dict with all 18 feature keys; missing values are None (NaN-passthrough
    for XGBoost/LightGBM; LogReg imputes per-participant median at train time).
    """
    t0, t1 = window
    w = dfs.filter((pl.col("sg_time_s") >= t0) & (pl.col("sg_time_s") < t1))

    # Signal-type slices (each signal type occupies its own rows in the canonical format)
    gsr = w.filter(pl.col("gsr_phasic").is_not_null()).sort("sg_time_s")
    st = w.filter(pl.col("skin_temp_c").is_not_null()).sort("sg_time_s")
    acc = w.filter(pl.col("acc_svm").is_not_null())
    _empty = pl.DataFrame()
    ann_eng  = w.filter(pl.col("engagement").is_not_null()) if "engagement" in dfs.columns else _empty
    ann_gaze = w.filter(pl.col("gaze").is_not_null())       if "gaze"       in dfs.columns else _empty
    ann_perf = w.filter(pl.col("performance").is_not_null()) if "performance" in dfs.columns else _empty

    window_s: float = t1 - t0
    amp_min: float = config["eda_amplitude_min"]
    acc_threshold: float = config["acc_svm_artifact_threshold"]
    condition: str = meta["condition"]
    duration: float | None = meta.get("total_session_duration_s")

    # -------------------------------------------------------------------------
    # EDA phasic — peak detection (artifact-gated rows excluded via gsr_phasic filter)
    # -------------------------------------------------------------------------
    if len(gsr) > 0:
        phasic = gsr["gsr_phasic"].to_numpy()
        valid_phasic = phasic[~np.isnan(phasic)]
        if len(valid_phasic) > 0:
            peaks, _ = find_peaks(valid_phasic, height=amp_min)
            peak_count = float(len(peaks))
        else:
            peak_count = 0.0
    else:
        peak_count = 0.0  # spec: fully null GSR → 0 (no peaks measurable)

    peak_freq = peak_count / (window_s / 60.0)  # peaks per minute

    # -------------------------------------------------------------------------
    # EDA tonic
    # -------------------------------------------------------------------------
    gsr_tonic_mean: float | None
    gsr_tonic_slope: float | None
    if len(gsr) > 0:
        times = gsr["sg_time_s"].to_numpy()
        tonic = gsr["gsr_tonic"].to_numpy()
        valid_t = ~np.isnan(tonic)
        gsr_tonic_mean = float(np.mean(tonic[valid_t])) if valid_t.any() else None
        gsr_tonic_slope = (
            float(np.polyfit(times[valid_t], tonic[valid_t], 1)[0])
            if valid_t.sum() >= 2
            else None
        )
    else:
        gsr_tonic_mean = None
        gsr_tonic_slope = None

    # -------------------------------------------------------------------------
    # GSR z-score — uses raw gsr_us (not phasic) vs population baseline
    # -------------------------------------------------------------------------
    gsr_raw_rows = w.filter(pl.col("gsr_us").is_not_null())
    subject_norm_gsr_z: float | None
    if len(gsr_raw_rows) > 0:
        gsr_raw = gsr_raw_rows["gsr_us"].to_numpy()
        subject_norm_gsr_z = float(
            (np.mean(gsr_raw) - norm_stats["gsr_mean"]) / norm_stats["gsr_std"]
        )
    else:
        subject_norm_gsr_z = None

    # -------------------------------------------------------------------------
    # Skin temperature
    # -------------------------------------------------------------------------
    skin_temp_mean: float | None
    skin_temp_derivative: float | None
    if len(st) > 0:
        temps = st["skin_temp_c"].to_numpy()
        valid_s = ~np.isnan(temps)
        skin_temp_mean = float(np.mean(temps[valid_s])) if valid_s.any() else None
        if valid_s.sum() >= 2:
            times_st = st["sg_time_s"].to_numpy()
            skin_temp_derivative = float(
                np.polyfit(times_st[valid_s], temps[valid_s], 1)[0]
            )
        else:
            skin_temp_derivative = None  # spec: < 2 valid rows → null
    else:
        skin_temp_mean = None
        skin_temp_derivative = None

    subject_norm_st_z: float | None = (
        float((skin_temp_mean - norm_stats["st_mean"]) / norm_stats["st_std"])
        if skin_temp_mean is not None
        else None
    )

    # -------------------------------------------------------------------------
    # Accelerometer
    # -------------------------------------------------------------------------
    acc_svm_mean: float | None
    acc_svm_std: float | None
    acc_svm_max: float | None
    acc_svm_above_ratio: float | None
    if len(acc) > 0:
        acc_vals = acc["acc_svm"].drop_nulls().to_numpy()
        if len(acc_vals) > 0:
            acc_svm_mean = float(np.mean(acc_vals))
            acc_svm_std = float(np.std(acc_vals))
            acc_svm_max = float(np.max(acc_vals))
            acc_svm_above_ratio = float((acc_vals > acc_threshold).sum() / len(acc_vals))
        else:
            acc_svm_mean = acc_svm_std = acc_svm_max = acc_svm_above_ratio = None
    else:
        acc_svm_mean = acc_svm_std = acc_svm_max = acc_svm_above_ratio = None

    # -------------------------------------------------------------------------
    # Contextual + temporal
    # -------------------------------------------------------------------------
    condition_lpe = 1 if condition == "LPE" else 0
    condition_hpe = 1 if condition == "HPE" else 0
    session_elapsed_ratio: float | None = (t0 / duration) if duration else None

    # -------------------------------------------------------------------------
    # Annotation features (training-only; null for baseline participants)
    # -------------------------------------------------------------------------
    gaze_off_task_ratio: float | None
    performance_failure_rate: float | None
    engagement_class_mode: int | None

    gaze_vals = ann_gaze["gaze"].to_numpy() if len(ann_gaze) > 0 else np.array([])
    gaze_off_task_ratio = (
        float((gaze_vals == 0).sum() / len(gaze_vals)) if len(gaze_vals) > 0 else None
    )

    perf_vals = ann_perf["performance"].to_numpy() if len(ann_perf) > 0 else np.array([])
    performance_failure_rate = (
        float((perf_vals == 1).sum() / len(perf_vals)) if len(perf_vals) > 0 else None
    )

    eng_vals = ann_eng["engagement"].to_numpy() if len(ann_eng) > 0 else np.array([])
    if len(eng_vals) > 0:
        values, counts = np.unique(eng_vals, return_counts=True)
        engagement_class_mode = int(values[np.argmax(counts)])
    else:
        engagement_class_mode = None

    return {
        "gsr_phasic_peak_count": peak_count,
        "gsr_phasic_peak_freq": peak_freq,
        "gsr_tonic_mean": gsr_tonic_mean,
        "gsr_tonic_slope": gsr_tonic_slope,
        "subject_norm_gsr_z": subject_norm_gsr_z,
        "skin_temp_mean": skin_temp_mean,
        "skin_temp_derivative": skin_temp_derivative,
        "subject_norm_st_z": subject_norm_st_z,
        "acc_svm_mean": acc_svm_mean,
        "acc_svm_std": acc_svm_std,
        "acc_svm_max": acc_svm_max,
        "acc_svm_above_threshold_ratio": acc_svm_above_ratio,
        "condition_lpe": condition_lpe,
        "condition_hpe": condition_hpe,
        "session_elapsed_ratio": session_elapsed_ratio,
        "gaze_off_task_ratio": gaze_off_task_ratio,
        "performance_failure_rate": performance_failure_rate,
        "engagement_class_mode": engagement_class_mode,
    }
