"""Video display widgets and frame conversion helpers."""
from __future__ import annotations

from typing import Optional

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel


def frame_to_pixmap(frame) -> QPixmap:
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb_frame.shape
    image = QImage(
        rgb_frame.data,
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image)


class VideoCanvas(QLabel):
    """Aspect-preserving video display surface."""

    def __init__(self):
        super().__init__("请选择视频")
        self._source_pixmap: Optional[QPixmap] = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setStyleSheet(
            "QLabel { background: #0b0d10; color: #9aa0a6; border: 1px solid #2f3338; }"
        )

    def set_frame(self, frame):
        self._source_pixmap = frame_to_pixmap(frame)
        self._update_scaled_pixmap()

    def clear_frame(self):
        self._source_pixmap = None
        self.setPixmap(QPixmap())
        self.setText("请选择视频")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setText("")
        self.setPixmap(scaled)
