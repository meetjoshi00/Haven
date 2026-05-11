"""Population baseline normalisation from P01–P19 (baseline condition).

NOTES.md decision: use population mean/std from baseline group, not per-subject.
Baseline participants have no LPE/HPE condition, so they serve as the reference population
for z-score normalisation applied during feature extraction.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def build_population_baseline(canonical_dir: Path, models_dir: Path) -> dict:
    """Compute GSR + ST population stats from all baseline participants (P01–P19).

    Reads condition=baseline canonical Parquets, concatenates GSR/ST columns,
    and computes mean/std ignoring nulls (Polars default). Saves result to
    models_dir/population_baseline.json and returns the dict.
    """
    baseline_dir = canonical_dir / "condition=baseline"
    if not baseline_dir.exists():
        raise FileNotFoundError(f"Baseline directory not found: {baseline_dir}")

    frames: list[pl.DataFrame] = []
    for p_dir in sorted(baseline_dir.iterdir()):
        if not p_dir.is_dir():
            continue
        parquet_path = p_dir / "data.parquet"
        if not parquet_path.exists():
            logger.warning("Missing baseline parquet: %s", parquet_path)
            continue
        frames.append(
            pl.read_parquet(parquet_path).select(["gsr_us", "skin_temp_c"])
        )

    if not frames:
        raise RuntimeError("No baseline parquets found under %s" % baseline_dir)

    combined = pl.concat(frames)
    row = combined.select([
        pl.col("gsr_us").mean().alias("gsr_mean"),
        pl.col("gsr_us").std().alias("gsr_std"),
        pl.col("skin_temp_c").mean().alias("st_mean"),
        pl.col("skin_temp_c").std().alias("st_std"),
    ]).row(0, named=True)

    baseline = {
        "gsr_mean": row["gsr_mean"],
        "gsr_std": row["gsr_std"],
        "st_mean": row["st_mean"],
        "st_std": row["st_std"],
        "n_participants": len(frames),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    models_dir.mkdir(parents=True, exist_ok=True)
    out_path = models_dir / "population_baseline.json"
    out_path.write_text(json.dumps(baseline, indent=2))
    logger.info(
        "Population baseline written to %s (n=%d, gsr_mean=%.4f, gsr_std=%.4f)",
        out_path, baseline["n_participants"], baseline["gsr_mean"], baseline["gsr_std"],
    )
    return baseline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _root = Path(__file__).parent.parent.parent
    baseline = build_population_baseline(
        _root / "ml" / "data" / "canonical",
        _root / "ml" / "models",
    )
    print(baseline)
