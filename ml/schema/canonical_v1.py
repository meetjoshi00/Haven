"""Canonical schema v1.0 — Pydantic models for documentation and API-level validation."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator


class CanonicalRecord(BaseModel):
    """One signal row at its native timestamp. Non-source columns are null."""

    participant_id: str
    source_dataset: str
    schema_version: str
    condition: str                        # "baseline" | "LPE" | "HPE"
    sg_time_s: float                      # session-relative seconds, native to source signal
    unix_time: Optional[float] = None     # null for annotation-only rows (no E4 timestamp)
    gsr_us: Optional[float] = None        # μS, 4Hz; null if artifact-gated or zero-nulled
    skin_temp_c: Optional[float] = None   # °C, 4Hz; null if below st_null_below_c
    acc_x: Optional[float] = None         # g, 32Hz
    acc_y: Optional[float] = None
    acc_z: Optional[float] = None
    acc_svm: Optional[float] = None       # pre-computed scalar velocity magnitude
    engagement: Optional[int] = None      # 0/1/2, 60Hz; null for baseline
    gaze: Optional[int] = None            # 0/1, 60Hz; null for baseline
    performance: Optional[int] = None     # 0/1, event-based; null for baseline
    intervention_type: Optional[str] = None  # "none"|"discrete"|"continuous"; null for baseline
    age: Optional[int] = None             # from paper Table 1; None if not yet confirmed
    diagnosis: Optional[str] = None       # "ASD"|"ASD,ID"|"ADHD"
    nasa_tlx_weighted: Optional[float] = None  # null for baseline
    sus_score: Optional[float] = None          # null for baseline

    @field_validator("condition")
    @classmethod
    def _check_condition(cls, v: str) -> str:
        if v not in {"baseline", "LPE", "HPE"}:
            raise ValueError(f"condition must be baseline|LPE|HPE, got {v!r}")
        return v

    @field_validator("intervention_type")
    @classmethod
    def _check_itype(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"none", "discrete", "continuous"}:
            raise ValueError(f"intervention_type must be none|discrete|continuous, got {v!r}")
        return v

    @field_validator("diagnosis")
    @classmethod
    def _check_diagnosis(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"ASD", "ASD,ID", "ADHD"}:
            raise ValueError(f"diagnosis must be ASD|ASD,ID|ADHD, got {v!r}")
        return v


class InterventionRecord(BaseModel):
    """Intervention summary for one participant × condition pair."""

    participant_id: str
    condition: str
    intervention_type: str                     # "none" | "discrete" | "continuous"
    discrete_timestamps_s: list[float] = []    # SGTime seconds; populated only for discrete type

    @field_validator("intervention_type")
    @classmethod
    def _check_itype(cls, v: str) -> str:
        if v not in {"none", "discrete", "continuous"}:
            raise ValueError(f"intervention_type must be none|discrete|continuous, got {v!r}")
        return v
