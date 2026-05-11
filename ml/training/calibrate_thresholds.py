"""L1 Phase 5 — threshold calibration from OOF predictions.

Reads oof_predictions.parquet (written by Phase 4), filters to label=1 AND
label_source="discrete", computes percentile distribution, writes risk_calibration.json.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

_ROOT         = Path(__file__).parent.parent.parent
_FEATURES_DIR = _ROOT / "ml" / "data" / "features"
_MODELS_DIR   = _ROOT / "ml" / "models"


def calibrate(config: dict) -> dict:
    """Compute risk_score percentile distribution from OOF predictions.

    Filters to label=1 AND label_source="discrete" — captures the
    pre-intervention spike distribution that L2 thresholds against.
    Continuous participants (label=1 entire session) are excluded because
    their scores reflect average elevated state, not the intervention trigger.

    Returns the calibration dict (also written to ml/models/risk_calibration.json).
    """
    oof_path = _FEATURES_DIR / "oof_predictions.parquet"
    if not oof_path.exists():
        raise FileNotFoundError(
            f"OOF predictions not found: {oof_path}. Run Phase 4 first."
        )

    oof = pl.read_parquet(oof_path)
    calibration_rows = oof.filter(
        (pl.col("label") == 1) & (pl.col("label_source") == "discrete")
    )
    scores = calibration_rows["oof_risk_score"].to_numpy()

    if len(scores) == 0:
        raise ValueError(
            "No qualifying rows (label=1, label_source='discrete') in oof_predictions.parquet. "
            "Verify Phase 4 ran correctly and OOF file has expected columns."
        )

    q10, q25, q50, q75, q90 = np.percentile(scores, [10, 25, 50, 75, 90])

    calibration = {
        "q10":           float(q10),
        "q25":           float(q25),
        "q50":           float(q50),
        "q75":           float(q75),
        "q90":           float(q90),
        "n_samples":     int(len(scores)),
        "model_version": config.get("model_version", "v1.0"),
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
    }

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _MODELS_DIR / "risk_calibration.json"
    out_path.write_text(json.dumps(calibration, indent=2))
    logger.info("risk_calibration.json written: %s", out_path)

    _print_milestone(calibration)
    return calibration


def calibrate_from_scores(scores: np.ndarray, config: dict, out_path: Path) -> dict:
    """Calibrate from a pre-filtered risk_score array (label=1, discrete already applied).

    Same computation as calibrate() but takes scores directly instead of reading parquet.
    Used by to_onnx.py to write risk_calibration_wearable.json from wearable OOF.
    """
    if len(scores) == 0:
        raise ValueError(
            "No qualifying scores provided. Verify OOF generation and label filtering."
        )

    q10, q25, q50, q75, q90 = np.percentile(scores, [10, 25, 50, 75, 90])

    calibration = {
        "q10":           float(q10),
        "q25":           float(q25),
        "q50":           float(q50),
        "q75":           float(q75),
        "q90":           float(q90),
        "n_samples":     int(len(scores)),
        "model_version": config.get("model_version", "v1.0"),
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(calibration, indent=2))
    logger.info("%s written: %s", out_path.name, out_path)

    _print_milestone(calibration, header=out_path.stem.upper().replace("_", " "))
    return calibration


def _print_milestone(cal: dict, header: str = "THRESHOLD CALIBRATION") -> None:
    print("\n" + "=" * 55)
    print(f"PHASE 5 — {header}")
    print("=" * 55)
    print(f"\n  n_samples (label=1, discrete): {cal['n_samples']}")
    print(f"\n  {'Percentile':<26} {'Risk Score':>10}")
    print(f"  {'-'*26} {'-'*10}")
    for key, label in [
        ("q10", "q10"),
        ("q25", "q25  [L2 default risk_score_gte]"),
        ("q50", "q50"),
        ("q75", "q75"),
        ("q90", "q90"),
    ]:
        print(f"  {label:<36} {cal[key]:>10.4f}")
    print(f"\n  model_version: {cal['model_version']}")
    print(f"  calibrated_at: {cal['calibrated_at']}")
    print("\n" + "=" * 55)
