"""Export type definitions shared by UI and export services."""
from __future__ import annotations

from enum import Enum


class ExportType(Enum):
    """Supported experiment-specific Excel export layouts."""

    LOOMING = "looming"
    TRAINING = "training"
    OFC = "ofc"
    TEST = "test"
