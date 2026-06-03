"""Dialog and canvas for selecting a top/bottom split line."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from services.video_crop_service import clamp_split_ratio
from views.qt.widgets.video_canvas import frame_to_pixmap


class SplitPreviewCanvas(QLabel):
    """Preview surface with a draggable horizontal split line."""

    split_changed = Signal(float)

    def __init__(self, frame, split_ratio: float = 0.5):
        super().__init__()
        self._source_pixmap = frame_to_pixmap(frame)
        self._split_ratio = clamp_split_ratio(split_ratio)
        self._display_rect = QRect()
        self._dragging = False
        self.setMinimumSize(720, 420)
        self.setMouseTracking(True)
        self.setStyleSheet("QLabel { background: #0b0d10; border: 1px solid #444b55; }")

    @property
    def split_ratio(self) -> float:
        return self._split_ratio

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b0d10"))
        if self._source_pixmap.isNull():
            return

        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = (self.width() - scaled.width()) // 2
        top = (self.height() - scaled.height()) // 2
        self._display_rect = QRect(left, top, scaled.width(), scaled.height())
        painter.drawPixmap(left, top, scaled)

        split_y = int(self._display_rect.top() + self._display_rect.height() * self._split_ratio)
        painter.setPen(QPen(QColor("#f4b400"), 3))
        painter.drawLine(self._display_rect.left(), split_y, self._display_rect.right(), split_y)
        painter.setPen(QPen(QColor("#111418"), 1))
        painter.setBrush(QColor("#f4b400"))
        painter.drawEllipse(QPoint(self._display_rect.center().x(), split_y), 7, 7)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._set_split_from_y(int(event.position().y()))

    def mouseMoveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        if self._dragging:
            self._set_split_from_y(int(event.position().y()))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._set_split_from_y(int(event.position().y()))

    def leaveEvent(self, event):
        if not self._dragging:
            self.unsetCursor()
        super().leaveEvent(event)

    def _set_split_from_y(self, y: int):
        if self._display_rect.height() <= 0:
            return
        ratio = (y - self._display_rect.top()) / max(1, self._display_rect.height())
        self._split_ratio = clamp_split_ratio(ratio)
        self.split_changed.emit(self._split_ratio)
        self.update()


class SplitPreviewDialog(QDialog):
    """Dialog for choosing a horizontal top/bottom split."""

    def __init__(self, frame, split_ratio: float = 0.5, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("拆分上下鼠")
        self.resize(820, 560)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("拖动黄色水平线设置上下两只鼠的分割位置。上方为 _1，下方为 _2。"))
        self.preview = SplitPreviewCanvas(frame, split_ratio)
        layout.addWidget(self.preview, 1)
        self.ratio_label = QLabel()
        layout.addWidget(self.ratio_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.preview.split_changed.connect(self._update_ratio_label)
        self._update_ratio_label(self.preview.split_ratio)

    @property
    def split_ratio(self) -> float:
        return self.preview.split_ratio

    def _update_ratio_label(self, ratio: float):
        self.ratio_label.setText(f"当前分割比例: {ratio:.3f}")
