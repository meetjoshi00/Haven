"""Abstract base class for all dataset adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import polars as pl

from ml.schema.canonical_v1 import InterventionRecord


class BaseAdapter(ABC):
    def __init__(self, raw_dir: Path, config: dict) -> None:
        self.raw_dir = raw_dir
        self.config = config

    @abstractmethod
    def load(
        self, participant_id: str, condition: str
    ) -> tuple[pl.DataFrame, InterventionRecord, dict]:
        """Read one participant × condition.

        Returns:
            df: canonical Polars DataFrame (all signal rows, native timestamps, nulls for non-source columns)
            intervention: InterventionRecord with type + discrete timestamps
            meta: dict with age, diagnosis, nasa_tlx_weighted, sus_score, total_session_duration_s
        """
        ...

    @abstractmethod
    def list_participants(self) -> list[tuple[str, str]]:
        """All (participant_id, condition) pairs this adapter can produce."""
        ...
