"""Per-video session state for the Qt workbench."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QUndoStack

from models.annotation_model import AnnotationModel
from services.video_crop_service import CROP_LOWER, CROP_UPPER, clamp_split_ratio
from views.qt.widgets.video_canvas import VideoCanvas


def session_metadata_values(
    source_path: str,
    logical_path: str,
    crop_role: Optional[str],
    split_ratio: Optional[float],
) -> dict:
    metadata = {
        "source_video_path": source_path,
        "source_filename": Path(source_path).name,
        "logical_filename": Path(logical_path).name,
    }
    if crop_role in {CROP_UPPER, CROP_LOWER} and split_ratio is not None:
        metadata.update(
            {
                "crop_role": crop_role,
                "split_ratio": clamp_split_ratio(split_ratio),
            }
        )
    return metadata


def session_metadata(session: "VideoSession") -> dict:
    return session_metadata_values(
        session.source_path,
        session.logical_path,
        session.crop_role,
        session.split_ratio,
    )


@dataclass
class VideoSession:
    """Per-tab logical video state."""

    source_path: str
    logical_path: str
    title: str
    canvas: VideoCanvas
    annotation_model: AnnotationModel
    undo_stack: QUndoStack
    crop_role: Optional[str] = None
    split_ratio: Optional[float] = None
    loaded_sidecar: bool = False
    metadata_dirty: bool = False
