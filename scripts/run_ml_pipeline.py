"""L1 ML pipeline orchestrator.

Phase 1: raw CSV → canonical Parquet   (adapter ingestion, all 57 participants)
Phase 2: artifact gate + EDA decompose -> data_preprocessed.parquet (per session)
Phase 3: feature extraction + labels   -> feature_matrix_v1.parquet
Phase 4: multi-algorithm CV + blind test -> best_model_meta.json + MLflow runs
Phase 5: threshold calibration + ONNX  -> risk_calibration.json + model_full/wearable.onnx
Coef:    LR + scaler export            -> model_full_coef.json + model_wearable_coef.json

Usage (new --phase form):
    python scripts/run_ml_pipeline.py --phase adapter    # Phase 1: raw CSV → canonical Parquet
    python scripts/run_ml_pipeline.py --phase preprocess # Phase 2: artifact gate + EDA
    python scripts/run_ml_pipeline.py --phase features   # Phase 3: feature extraction
    python scripts/run_ml_pipeline.py --phase train      # Phase 4+5+coef (L2 recalibration path)
    python scripts/run_ml_pipeline.py --phase export     # Phase 5+coef (ONNX refresh)
    python scripts/run_ml_pipeline.py --phase all        # Full end-to-end

Legacy flags (still work):
    python scripts/run_ml_pipeline.py              # Phase 2 (skip done) + Phase 3
    python scripts/run_ml_pipeline.py --phase2     # Phase 2 only
    python scripts/run_ml_pipeline.py --phase3     # Phase 3 only (Phase 2 must be done)
    python scripts/run_ml_pipeline.py --phase4     # Phase 4 only (Phase 3 must be done)
    python scripts/run_ml_pipeline.py --phase5     # Phase 5 only (Phase 4 must be done)
    python scripts/run_ml_pipeline.py --force      # Re-run Phase 2 even if already done

Requires:
  - ml/data/raw/          Raw Engagnition CSVs + XLSX
  - ml/models/population_baseline.json
  - ml/config.yaml
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import polars as pl
import yaml

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from ml.adapters.engagnition_v1 import EngagnitionV1Adapter
from ml.features.extract import extract_features
from ml.features.label import assign_label
from ml.features.window import generate_windows
from ml.preprocessing.artifact_gate import apply_artifact_gate
from ml.preprocessing.eda_decompose import decompose_session

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_ml_pipeline")

_RAW_DIR       = _ROOT / "ml" / "data" / "raw"
_CANONICAL_DIR = _ROOT / "ml" / "data" / "canonical"
_FEATURES_DIR  = _ROOT / "ml" / "data" / "features"
_MODELS_DIR    = _ROOT / "ml" / "models"

_CONTINUOUS_PARTICIPANTS = [
    ("P26", "LPE"), ("P27", "LPE"), ("P29", "LPE"),
    ("P44", "HPE"), ("P48", "HPE"), ("P55", "HPE"),
]

_FEATURE_COLS = [
    "gsr_phasic_peak_count", "gsr_phasic_peak_freq",
    "gsr_tonic_mean", "gsr_tonic_slope", "subject_norm_gsr_z",
    "skin_temp_mean", "skin_temp_derivative", "subject_norm_st_z",
    "acc_svm_mean", "acc_svm_std", "acc_svm_max", "acc_svm_above_threshold_ratio",
    "condition_lpe", "condition_hpe", "session_elapsed_ratio",
    "gaze_off_task_ratio", "performance_failure_rate", "engagement_class_mode",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(_ROOT / "ml" / "config.yaml") as f:
        return yaml.safe_load(f)


def _load_norm_stats() -> dict:
    with open(_MODELS_DIR / "population_baseline.json") as f:
        return json.load(f)


def _canonical_path(pid: str, cond: str) -> Path:
    return _CANONICAL_DIR / f"condition={cond}" / f"participant={pid}" / "data.parquet"


def _preprocessed_path(pid: str, cond: str) -> Path:
    return _CANONICAL_DIR / f"condition={cond}" / f"participant={pid}" / "data_preprocessed.parquet"


def _all_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i in range(1, 20):
        pairs.append((f"P{i:02d}", "baseline"))
    for i in range(20, 39):
        pairs.append((f"P{i:02d}", "LPE"))
    for i in range(39, 58):
        pairs.append((f"P{i:02d}", "HPE"))
    return pairs


# ---------------------------------------------------------------------------
# Phase 1 — Adapter ingestion
# ---------------------------------------------------------------------------

def run_phase1(config: dict, force: bool = False) -> None:
    """Ingest raw CSVs → canonical Parquet for all 57 participants.

    Reads Engagnition CSVs from ml/data/raw/. Skips participants whose
    canonical Parquet already exists unless force=True.
    """
    adapter = EngagnitionV1Adapter(raw_dir=_RAW_DIR, config=config)
    pairs = _all_pairs()
    done = skipped = failed = 0

    for pid, cond in pairs:
        dst = _canonical_path(pid, cond)
        if dst.exists() and not force:
            skipped += 1
            continue
        try:
            df, _, _ = adapter.load(pid, cond)
            dst.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(dst)
            logger.info("  Phase 1: %s %s → %d rows", pid, cond, len(df))
            done += 1
        except Exception as exc:
            logger.error("  Phase 1: FAILED for %s %s: %s", pid, cond, exc)
            failed += 1

    logger.info(
        "Phase 1 complete: %d ingested, %d skipped (already done), %d failed",
        done, skipped, failed,
    )


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------

def run_phase2(config: dict, force: bool = False) -> None:
    """Artifact gate + EDA decompose for all 57 sessions.

    Skips sessions whose data_preprocessed.parquet already exists unless force=True.
    Reads data.parquet (Phase 1 output) from the canonical directory.
    """
    pairs = _all_pairs()
    done = skipped = missing = failed = 0

    for pid, cond in pairs:
        src = _canonical_path(pid, cond)
        dst = _preprocessed_path(pid, cond)

        if not src.exists():
            logger.warning("  Phase 2: missing canonical Parquet for %s %s — skipping", pid, cond)
            missing += 1
            continue

        if dst.exists() and not force:
            skipped += 1
            continue

        try:
            df = pl.read_parquet(src)
            df = apply_artifact_gate(df, config)
            df = decompose_session(df, config)
            dst.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(dst)
            logger.info("  Phase 2: %s %s -> %s rows", pid, cond, len(df))
            done += 1
        except Exception as exc:
            logger.error("  Phase 2: FAILED for %s %s: %s", pid, cond, exc)
            failed += 1

    logger.info(
        "Phase 2 complete: %d processed, %d skipped (already done), %d missing canonical, %d failed",
        done, skipped, missing, failed,
    )


# ---------------------------------------------------------------------------
# Phase 3
# ---------------------------------------------------------------------------

def run_phase3(config: dict, norm_stats: dict) -> pl.DataFrame:
    """Feature extraction + label assignment for all preprocessed sessions."""
    adapter = EngagnitionV1Adapter(raw_dir=_RAW_DIR, config=config)

    window_s: float = config["window_size_s"]
    stride_s: float = config["stride_s"]
    lookahead_s: float = config["lookahead_s"]

    rows: list[dict] = []
    pairs = _all_pairs()

    for i, (pid, cond) in enumerate(pairs):
        preproc = _preprocessed_path(pid, cond)
        if not preproc.exists():
            logger.warning("  Phase 3: missing preprocessed Parquet for %s %s — skipping", pid, cond)
            continue

        df = pl.read_parquet(preproc)
        _, intervention, meta = adapter.load(pid, cond)

        sg_min = float(df["sg_time_s"].min())
        sg_max = float(df["sg_time_s"].max())
        windows = generate_windows(sg_min, sg_max, window_s, stride_s)

        itype = intervention.intervention_type
        for win in windows:
            feats = extract_features(win, df, norm_stats, meta, config)
            label, label_source = assign_label(win, intervention, lookahead_s, itype)
            rows.append({
                "participant_id": pid,
                "condition": cond,
                "window_start_s": win[0],
                "window_end_s": win[1],
                "label": label,
                "label_source": label_source,
                **feats,
            })

        logger.info("  Phase 3: [%02d/%d] %s %s — %d windows, itype=%s",
                    i + 1, len(pairs), pid, cond, len(windows), itype)

    logger.info("Total windows: %d", len(rows))

    fm = pl.DataFrame(rows, infer_schema_length=len(rows)).with_columns([
        pl.col("label").cast(pl.Int8),
        pl.col("condition_lpe").cast(pl.Int8),
        pl.col("condition_hpe").cast(pl.Int8),
        pl.col("engagement_class_mode").cast(pl.Int8),
    ])

    _FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _FEATURES_DIR / "feature_matrix_v1.parquet"
    fm.write_parquet(out_path)
    logger.info("Feature matrix written: %s  (%d rows x %d cols)", out_path, *fm.shape)

    return fm


# ---------------------------------------------------------------------------
# Milestone verification
# ---------------------------------------------------------------------------

def _print_milestones(fm: pl.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("PHASE 3 MILESTONE VERIFICATION")
    print("=" * 60)

    print("\n--- Class Balance ---")
    balance = (
        fm.group_by(["label_source", "label"])
        .len()
        .rename({"len": "count"})
        .sort(["label_source", "label"])
    )
    print(balance)

    print("\n--- P22 LPE label=1 windows ---")
    p22_pos = fm.filter(
        (pl.col("participant_id") == "P22") &
        (pl.col("condition") == "LPE") &
        (pl.col("label") == 1)
    ).select(["window_start_s", "window_end_s"])
    if len(p22_pos) > 0:
        print(p22_pos)
    else:
        print("  (none — verify intervention timestamps in InterventionData.xlsx)")

    print("\n--- Continuous participants: all label=1? ---")
    all_ok = True
    for pid, cond in _CONTINUOUS_PARTICIPANTS:
        subset = fm.filter(
            (pl.col("participant_id") == pid) & (pl.col("condition") == cond)
        )
        if len(subset) == 0:
            print(f"  {pid} {cond}: NO WINDOWS FOUND")
            all_ok = False
            continue
        pct1 = float(subset["label"].mean()) * 100
        status = "OK" if pct1 == 100.0 else "FAIL"
        print(f"  {pid} {cond}: {pct1:.1f}% label=1  [{status}]")
        if status == "FAIL":
            all_ok = False
    print(f"  Result: {'PASS' if all_ok else 'FAIL'}")

    print("\n--- Null % per feature ---")
    n = len(fm)
    for col in _FEATURE_COLS:
        null_pct = fm[col].is_null().sum() / n * 100
        bar = "#" * int(null_pct / 5)
        print(f"  {col:<42} {null_pct:5.1f}%  {bar}")

    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# Phase 4
# ---------------------------------------------------------------------------

def run_phase4(config: dict) -> dict:
    """Training CV — reads feature_matrix_v1.parquet, writes best_model_meta.json."""
    from ml.training.train import run_cv
    return run_cv(config)


# ---------------------------------------------------------------------------
# Phase 5
# ---------------------------------------------------------------------------

def run_phase5(config: dict) -> None:
    """Threshold calibration + ONNX export.

    Requires Phase 4 outputs: oof_predictions.parquet + feature_matrix_v1.parquet.
    Writes: risk_calibration.json + model_full.onnx + model_wearable.onnx
    """
    from ml.training.calibrate_thresholds import calibrate
    from ml.export.to_onnx import export_onnx
    calibrate(config)
    export_onnx(config)


# ---------------------------------------------------------------------------
# Coefficient export (for predict.py SHAP)
# ---------------------------------------------------------------------------

def run_coef_export(config: dict) -> None:
    """Train final LR on all participants, write coef + scaler stats for SHAP.

    Calls _train_with_smote() from ml.export.to_onnx for both feature sets.
    Writes (committed artifacts):
      ml/models/model_full_coef.json     — 18-feature LR coefficients
      ml/models/model_wearable_coef.json — 15-feature LR coefficients

    predict.py loads these at startup to compute analytical LR SHAP values
    without requiring sklearn at API inference time.
    """
    from ml.export.to_onnx import _train_with_smote, _load_all_features, _load_wearable_features

    fm       = pl.read_parquet(_FEATURES_DIR / "feature_matrix_v1.parquet")
    pids_all = fm["participant_id"].to_numpy()
    y_all    = fm["label"].to_numpy().astype(int)

    for feat_names, model_key in [
        (_load_all_features(),      "full"),
        (_load_wearable_features(), "wearable"),
    ]:
        X_all = fm.select(feat_names).to_numpy(allow_copy=True).astype(float)
        _, scaler, lr = _train_with_smote(X_all, y_all, pids_all)

        out = {
            "model_type":    model_key,
            "n_features":    len(feat_names),
            "feature_names": feat_names,
            "coef":          lr.coef_[0].tolist(),
            "intercept":     float(lr.intercept_[0]),
            "scaler_mean":   scaler.mean_.tolist(),
            "scaler_std":    scaler.scale_.tolist(),
        }
        out_path = _MODELS_DIR / f"model_{model_key}_coef.json"
        out_path.write_text(json.dumps(out, indent=2))
        logger.info(
            "Coef export: %s  (n_features=%d, n_coef=%d)",
            out_path.name, len(feat_names), len(out["coef"]),
        )

    logger.info("Coefficient export complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L1 ML pipeline")
    # New unified --phase argument
    parser.add_argument(
        "--phase",
        choices=["adapter", "preprocess", "features", "train", "export", "all"],
        help=(
            "adapter=raw CSV→Parquet | preprocess=artifact gate+EDA | "
            "features=feature extraction | train=Phase4+5+coef (L2 recalibration) | "
            "export=Phase5+coef | all=full end-to-end"
        ),
    )
    # Legacy flags (backward compat)
    parser.add_argument("--phase2", action="store_true", help="(legacy) Run Phase 2 only")
    parser.add_argument("--phase3", action="store_true", help="(legacy) Run Phase 3 only")
    parser.add_argument("--phase4", action="store_true", help="(legacy) Run Phase 4 only")
    parser.add_argument("--phase5", action="store_true", help="(legacy) Run Phase 5 only")
    parser.add_argument("--force",  action="store_true",
                        help="Force re-run Phase 1/2 even if output already exists")
    args = parser.parse_args()

    config = _load_config()

    # --- New --phase dispatch ---
    if args.phase == "adapter":
        logger.info("=== Phase 1: adapter ingestion ===")
        run_phase1(config, force=args.force)

    elif args.phase == "preprocess":
        logger.info("=== Phase 2: artifact gate + EDA decompose ===")
        run_phase2(config, force=args.force)

    elif args.phase == "features":
        logger.info("=== Phase 3: feature extraction + label assignment ===")
        norm_stats = _load_norm_stats()
        fm = run_phase3(config, norm_stats)
        _print_milestones(fm)

    elif args.phase == "train":
        logger.info("=== Phase 4: training + evaluation ===")
        run_phase4(config)
        logger.info("=== Phase 5: threshold calibration + ONNX export ===")
        run_phase5(config)
        logger.info("=== Coef export: LR + scaler stats for SHAP ===")
        run_coef_export(config)

    elif args.phase == "export":
        logger.info("=== Phase 5: threshold calibration + ONNX export ===")
        run_phase5(config)
        logger.info("=== Coef export: LR + scaler stats for SHAP ===")
        run_coef_export(config)

    elif args.phase == "all":
        logger.info("=== Phase 1: adapter ingestion ===")
        run_phase1(config, force=args.force)
        logger.info("=== Phase 2: artifact gate + EDA decompose ===")
        run_phase2(config, force=args.force)
        logger.info("=== Phase 3: feature extraction + label assignment ===")
        norm_stats = _load_norm_stats()
        fm = run_phase3(config, norm_stats)
        _print_milestones(fm)
        logger.info("=== Phase 4: training + evaluation ===")
        run_phase4(config)
        logger.info("=== Phase 5: threshold calibration + ONNX export ===")
        run_phase5(config)
        logger.info("=== Coef export: LR + scaler stats for SHAP ===")
        run_coef_export(config)

    else:
        # --- Legacy flag dispatch ---
        run_default = not args.phase2 and not args.phase3 and not args.phase4 and not args.phase5

        if args.phase2 or run_default:
            logger.info("=== Phase 2: artifact gate + EDA decompose ===")
            run_phase2(config, force=args.force)

        if args.phase3 or run_default:
            logger.info("=== Phase 3: feature extraction + label assignment ===")
            norm_stats = _load_norm_stats()
            fm = run_phase3(config, norm_stats)
            _print_milestones(fm)

        if args.phase4:
            logger.info("=== Phase 4: training + evaluation ===")
            run_phase4(config)

        if args.phase5:
            logger.info("=== Phase 5: threshold calibration + ONNX export ===")
            run_phase5(config)

    logger.info("Pipeline complete")
