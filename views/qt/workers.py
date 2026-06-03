"""Background workers used by the Qt workbench."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from services.freezing_detection_service import FreezingDetectionParams, FreezingDetectionService


class FreezingDetectionWorker(QObject):
    progress = Signal(float)
    finished = Signal(object, str)
    failed = Signal(str)

    def __init__(
        self,
        video_path: str,
        fps: float,
        total_frames: int,
        params: FreezingDetectionParams,
        logical_video_path: Optional[str] = None,
        crop_role: Optional[str] = None,
        split_ratio: Optional[float] = None,
    ):
        super().__init__()
        self.video_path = video_path
        self.logical_video_path = logical_video_path or video_path
        self.fps = fps
        self.total_frames = total_frames
        self.params = params
        self.crop_role = crop_role
        self.split_ratio = split_ratio
        self.service = FreezingDetectionService()

    def run(self):
        try:
            intervals = self.service.detect_freezing(
                self.video_path,
                self.fps,
                self.total_frames,
                self.params,
                self.progress.emit,
                self.crop_role,
                self.split_ratio,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(intervals, self.logical_video_path)
