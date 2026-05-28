"""Utilities for virtual horizontal video crops."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


CROP_UPPER = "upper"
CROP_LOWER = "lower"
MIN_SPLIT_RATIO = 0.05
MAX_SPLIT_RATIO = 0.95


def clamp_split_ratio(split_ratio: float) -> float:
    """Clamp a normalized split ratio to keep both crops visible."""
    return max(MIN_SPLIT_RATIO, min(float(split_ratio), MAX_SPLIT_RATIO))


def horizontal_crop_bounds(
    height: int,
    split_ratio: float,
    crop_role: Optional[str],
) -> tuple[int, int]:
    """Return ``(top, bottom)`` bounds for a virtual horizontal crop."""
    height = max(0, int(height))
    if height <= 1 or crop_role not in {CROP_UPPER, CROP_LOWER}:
        return 0, height

    split_ratio = clamp_split_ratio(split_ratio)
    split_y = int(round(height * split_ratio))
    split_y = max(1, min(split_y, height - 1))

    if crop_role == CROP_UPPER:
        return 0, split_y
    return split_y, height


def apply_horizontal_crop(
    frame: np.ndarray,
    crop_role: Optional[str],
    split_ratio: Optional[float],
) -> np.ndarray:
    """Apply a top/bottom virtual crop to a frame."""
    if crop_role not in {CROP_UPPER, CROP_LOWER} or split_ratio is None:
        return frame

    top, bottom = horizontal_crop_bounds(frame.shape[0], split_ratio, crop_role)
    return frame[top:bottom, :]


def logical_split_video_path(source_path: str, index: int) -> str:
    """Return the virtual child video path used for sidecars and exports."""
    path = Path(source_path)
    return str(path.with_name(f"{path.stem}_{index}{path.suffix}"))
