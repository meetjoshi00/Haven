"""NeuroKit2 cvxEDA decomposition — phasic (SCR) and tonic (SCL) components.

Operates on the artifact-gated canonical DataFrame. Filters to GSR-only rows
(gsr_us.is_not_null()), runs NeuroKit2 eda_process with method="cvxEDA", then
joins the phasic/tonic arrays back to the full DataFrame by sg_time_s.

Non-GSR rows (ACC, ST, annotation rows from the diagonal concat) receive null
phasic/tonic. Artifact-gated GSR rows are already null in gsr_us, so they are
absent from the filtered set and receive null after the join.
"""
from __future__ import annotations

import logging
from pathlib import Path

import neurokit2 as nk
import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

_NK2_MIN_SAMPLES = 8


def decompose_session(df: pl.DataFrame, config: dict) -> pl.DataFrame:
    """Add gsr_phasic and gsr_tonic columns via NeuroKit2 cvxEDA.

    Returns the input DataFrame with two new Float64 columns appended:
    - gsr_phasic: SCR (phasic) component
    - gsr_tonic:  SCL (tonic)  component

    Both are null for non-GSR rows and for artifact-gated GSR rows.
    """
    sampling_rate: int = int(config["gsr_sampling_rate_hz"])

    _null_cols = [
        pl.lit(None, dtype=pl.Float64).alias("gsr_phasic"),
        pl.lit(None, dtype=pl.Float64).alias("gsr_tonic"),
    ]

    has_flag_col = "gsr_artifact_flagged" in df.columns

    if has_flag_col:
        # Reconstruct full GSR time series: valid rows + artifact-gated rows (gaps).
        # After the cosmetic fix in artifact_gate.py, gsr_artifact_flagged=True only
        # on actual GSR rows whose gsr_us was nulled by artifact gating.
        all_gsr_df = df.filter(
            pl.col("gsr_us").is_not_null() | pl.col("gsr_artifact_flagged")
        ).sort("sg_time_s")
    else:
        all_gsr_df = df.filter(pl.col("gsr_us").is_not_null()).sort("sg_time_s")

    valid_count = all_gsr_df.filter(pl.col("gsr_us").is_not_null()).shape[0]
    if valid_count < _NK2_MIN_SAMPLES:
        logger.warning(
            "Too few valid GSR samples (%d < %d) — phasic/tonic set to null",
            valid_count, _NK2_MIN_SAMPLES,
        )
        return df.with_columns(_null_cols)

    # vals has NaN where gsr_us is null (artifact-gated gaps); Polars → numpy converts nulls to NaN
    vals = all_gsr_df["gsr_us"].to_numpy().astype(np.float64)

    if has_flag_col:
        artifact_mask = all_gsr_df["gsr_artifact_flagged"].to_numpy()
    else:
        artifact_mask = np.isnan(vals)

    valid_idx = np.where(~artifact_mask)[0]

    # Linearly interpolate across artifact-gated gaps so cvxEDA sees a contiguous signal.
    # np.interp extrapolates at edges using the nearest valid value (acceptable).
    if artifact_mask.any():
        eda_input = vals.copy()
        eda_input[artifact_mask] = np.interp(
            np.where(artifact_mask)[0], valid_idx, vals[valid_idx]
        )
    else:
        eda_input = vals

    try:
        # Skip eda_clean: biosppy filter requires >5Hz; at 4Hz it is a no-op and warns.
        # amplitude_min is for peak counting in Phase 3 feature extraction, not decomposition.
        phasic_df = nk.eda_phasic(eda_input, sampling_rate=sampling_rate, method="cvxEDA")
        phasic = phasic_df["EDA_Phasic"].to_numpy().astype(np.float64)
        tonic = phasic_df["EDA_Tonic"].to_numpy().astype(np.float64)
    except Exception as exc:
        logger.warning("cvxEDA failed (%s) — phasic/tonic set to null", exc)
        return df.with_columns(_null_cols)

    # Re-null interpolated positions — artifact-gated rows should not have phasic/tonic
    phasic[artifact_mask] = np.nan
    tonic[artifact_mask] = np.nan

    # Attach phasic/tonic only to valid GSR rows, then join back to full DataFrame
    valid_gsr_df = all_gsr_df.filter(pl.col("gsr_us").is_not_null())
    gsr_decomposed = valid_gsr_df.select("sg_time_s").with_columns([
        pl.Series("gsr_phasic", phasic[~artifact_mask], dtype=pl.Float64),
        pl.Series("gsr_tonic", tonic[~artifact_mask], dtype=pl.Float64),
    ])

    # Left join: valid GSR rows match by sg_time_s; all other rows get null
    return df.join(gsr_decomposed, on="sg_time_s", how="left")


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

    from ml.preprocessing.artifact_gate import apply_artifact_gate

    logging.basicConfig(level=logging.INFO)
    _root = Path(__file__).parent.parent.parent
    _config = yaml.safe_load((_root / "ml" / "config.yaml").read_text())

    _parquet = _find_first_annotated_parquet(_root / "ml" / "data" / "canonical")
    print(f"Testing on: {_parquet}")
    _df = pl.read_parquet(_parquet)
    _gated = apply_artifact_gate(_df, _config)
    _result = decompose_session(_gated, _config)

    _out_path = _parquet.parent / "data_preprocessed.parquet"
    _result.write_parquet(_out_path)
    print(f"Saved: {_out_path}  shape={_result.shape}")

    _gsr_rows = _result.filter(pl.col("gsr_us").is_not_null())
    print(_gsr_rows.select(["sg_time_s", "gsr_us", "gsr_phasic", "gsr_tonic"]).head(10))
