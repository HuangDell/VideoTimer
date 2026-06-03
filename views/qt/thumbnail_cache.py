"""OpenCV-backed thumbnail cache for timeline hover previews."""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

import cv2
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from services.video_crop_service import apply_horizontal_crop
from views.qt.widgets.video_canvas import frame_to_pixmap


class ThumbnailCache:
    """Small frame thumbnail cache backed by a dedicated OpenCV capture."""

    def __init__(self, max_items: int = 80):
        self.max_items = max_items
        self.capture = None
        self.total_frames = 0
        self.cache: OrderedDict[tuple[int, Optional[str], Optional[float]], QPixmap] = OrderedDict()

    def load_video(self, video_path: str, total_frames: int):
        self.release()
        self.capture = cv2.VideoCapture(video_path)
        self.total_frames = max(0, int(total_frames))
        self.cache.clear()

    def get(
        self,
        frame: int,
        size: QSize = QSize(180, 104),
        crop_role: Optional[str] = None,
        split_ratio: Optional[float] = None,
    ) -> Optional[QPixmap]:
        if self.capture is None or not self.capture.isOpened() or self.total_frames <= 0:
            return None
        frame = max(0, min(int(frame), max(0, self.total_frames - 1)))
        cache_key = (frame, crop_role, round(split_ratio, 6) if split_ratio is not None else None)
        if cache_key in self.cache:
            pixmap = self.cache.pop(cache_key)
            self.cache[cache_key] = pixmap
            return pixmap

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = self.capture.read()
        if not ok:
            return None
        image = apply_horizontal_crop(image, crop_role, split_ratio)
        pixmap = frame_to_pixmap(image).scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cache[cache_key] = pixmap
        while len(self.cache) > self.max_items:
            self.cache.popitem(last=False)
        return pixmap

    def release(self):
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.cache.clear()
