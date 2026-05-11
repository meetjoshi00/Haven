"""Motion artifact gating (Kleckner 2018).

Slides 30s windows (10s stride) over the ACC signal. Any window where >20% of
32Hz ACC samples exceed the threshold is flagged. All GSR samples in flagged
windows are nulled (conservative: if any covering window flags a sample, null it).

The canonical Parquet is a diagonal concat of signal streams — GSR rows are
identified by gsr_us.is_not_null(), ACC rows by acc_svm.is_not_null().
"""
from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def apply_artifact_gate(df: pl.DataFrame, config: dict) -> pl.DataFrame:
    """Null gsr_us for windows where ACC motion exceeds threshold.

    Returns the same DataFrame with:
    - gsr_us: additionally nulled for artifact-contaminated samples
    - gsr_artifact_flagged (Bool): True for every row whose sg_time_s falls
      in at least one artifact-flagged window
    """
    window_s: float = float(config["window_size_s"])
    stride_s: float = float(config["stride_s"])
    threshold: float = float(config["acc_svm_artifact_threshold"])
    ratio: float = float(config["acc_svm_artifact_ratio"])

    t_min: float = df["sg_time_s"].min()
    t_max: float = df["sg_time_s"].max()

    flagged_ranges: list[tuple[float, float]] = []
    t_start = t_min
    while t_start + window_s <= t_max:
        t_end = t_start + window_s
        acc_window = df.filter(
            (pl.col("sg_time_s") >= t_start)
            & (pl.col("sg_time_s") < t_end)
            & pl.col("acc_svm").is_not_null()
        )["acc_svm"]
        total = len(acc_window)
        if total > 0 and (acc_window > threshold).sum() / total > ratio:
            flagged_ranges.append((t_start, t_end))
        t_start += stride_s

    if flagged_ranges:
        logger.info(
            "Artifact gate: %d/%d windows flagged",
            len(flagged_ranges),
            int((t_max - t_min - window_s) / stride_s) + 1,
        )

    if not flagged_ranges:
        return df.with_columns(pl.lit(False).alias("gsr_artifact_flagged"))

    # Build time-range expression: True if sg_time_s falls in any flagged window
    ts0, te0 = flagged_ranges[0]
    in_flagged_window = (pl.col("sg_time_s") >= ts0) & (pl.col("sg_time_s") < te0)
    for ts, te in flagged_ranges[1:]:
        in_flagged_window = in_flagged_window | (
            (pl.col("sg_time_s") >= ts) & (pl.col("sg_time_s") < te)
        )

    # Only flag rows that are actual GSR rows (gsr_us not null before any nulling).
    # Evaluated against current gsr_us, so ACC/ST/annotation rows never get flagged.
    df = df.with_columns(
        (pl.col("gsr_us").is_not_null() & in_flagged_window).alias("gsr_artifact_flagged")
    )
    df = df.with_columns(
        pl.when(pl.col("gsr_artifact_flagged"))
        .then(pl.lit(None, dtype=pl.Float64))
        .otherwise(pl.col("gsr_us"))
        .alias("gsr_us")
    )
    return df


def _find_first_annotated_parquet(canonical_dir: Path) -> Path:
    """Return the first data.parquet from a non-baseline condition."""
    for cond_dir in sorted(canonical_dir.iterdir()):
        if not cond_dir.is_dir() or cond_dir.name == "condition=baseline":
            continue
        for p_dir in sorted(cond_dir.iterdir()):
            parquet = p_dir / "data.parquet"
            if parquet.exists():
                return parquet
    raise FileNotFoundError("No non-baseline canonical parquet found under %s" % canonical_dir)


if __name__ == "__main__":
    import yaml

    logging.basicConfig(level=logging.INFO)
    _root = Path(__file__).parent.parent.parent
    _config = yaml.safe_load((_root / "ml" / "config.yaml").read_text())
    _parquet = _find_first_annotated_parquet(_root / "ml" / "data" / "canonical")
    print(f"Testing on: {_parquet}")
    _df = pl.read_parquet(_parquet)
    _result = apply_artifact_gate(_df, _config)
    _flagged = _result.filter(pl.col("gsr_artifact_flagged")).shape[0]
    print(f"Artifact-flagged rows: {_flagged} / {len(_result)}")
    print(_result.filter(pl.col("gsr_us").is_not_null()).select(
        ["sg_time_s", "gsr_us", "gsr_artifact_flagged"]
    ).head(10))
