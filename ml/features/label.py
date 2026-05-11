from ml.schema.canonical_v1 import InterventionRecord


def assign_label(
    window: tuple[float, float],
    interventions: InterventionRecord,
    lookahead_s: float,
    itype: str,
) -> tuple[int, str]:
    """Return (label, label_source). label_source stored for diagnostics, not training."""
    _, t_end = window

    if itype == "none":
        return 0, "none"
    if itype == "continuous":
        return 1, "continuous"
    if itype == "discrete":
        for ts in interventions.discrete_timestamps_s:
            if t_end <= ts <= t_end + lookahead_s:
                return 1, "discrete"
        return 0, "discrete"
    raise ValueError(f"unknown intervention_type: {itype!r}")
