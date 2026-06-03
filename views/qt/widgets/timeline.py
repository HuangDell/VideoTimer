"""Timeline tracks for seeking and interval editing."""
from __future__ import annotations

from typing import Iterable, List, Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from models.annotation_model import AnnotationInterval
from utils.timeline_viewport import TimelineViewport


class ProgressTrackWidget(QWidget):
    """Seek-only progress track."""

    seek_requested = Signal(int)
    thumbnail_requested = Signal(int, QPoint)
    zoom_requested = Signal(int, float)

    def __init__(self, viewport: TimelineViewport):
        super().__init__()
        self.viewport = viewport
        self.current_frame = 0
        self._dragging = False
        self.setMouseTracking(True)
        self.setMinimumHeight(44)
        self.setStyleSheet("background: #171a1f;")

    def set_current_frame(self, frame: int):
        self.current_frame = self.viewport.clamp_frame(frame, seekable=True)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a1f"))

        track = self._track_rect()
        painter.setPen(QPen(QColor("#333841"), 1))
        painter.setBrush(QColor("#20242b"))
        painter.drawRoundedRect(track, 4, 4)

        if self.viewport.total_frames <= 0:
            painter.setPen(QColor("#8f969f"))
            painter.drawText(track, Qt.AlignmentFlag.AlignCenter, "加载视频后显示进度条")
            return

        painter.setPen(QPen(QColor("#2d323a"), 1))
        for fraction in (0.25, 0.5, 0.75):
            x = int(track.left() + track.width() * fraction)
            painter.drawLine(x, track.top(), x, track.bottom())

        fill_right = track.left()
        if self.current_frame >= self.viewport.visible_end_frame:
            fill_right = track.right()
        elif self.current_frame > self.viewport.visible_start_frame:
            fill_right = self._frame_to_x(self.current_frame)
        if fill_right > track.left():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#3f7ee8"))
            painter.drawRoundedRect(
                QRect(track.left(), track.top(), fill_right - track.left(), track.height()),
                4,
                4,
            )

        if self._is_frame_visible(self.current_frame):
            playhead_x = self._frame_to_x(self.current_frame)
            painter.setPen(QPen(QColor("#ff5a5f"), 2))
            painter.drawLine(playhead_x, track.top() - 7, playhead_x, track.bottom() + 7)
            painter.setBrush(QColor("#ff5a5f"))
            painter.drawEllipse(QPoint(playhead_x, track.center().y()), 5, 5)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.viewport.total_frames <= 0:
            return
        self._dragging = True
        self._seek_from_x(int(event.position().x()))
        event.accept()

    def mouseMoveEvent(self, event):
        if self.viewport.total_frames <= 0:
            return
        frame = self._x_to_frame(int(event.position().x()), seekable=True)
        self.thumbnail_requested.emit(frame, event.globalPosition().toPoint())
        if self._dragging:
            self.seek_requested.emit(frame)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging:
            self._seek_from_x(int(event.position().x()))
        self._dragging = False
        event.accept()

    def leaveEvent(self, event):
        self.thumbnail_requested.emit(-1, QPoint())
        super().leaveEvent(event)

    def wheelEvent(self, event):
        if (
            self.viewport.total_frames > 0
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.angleDelta().y() != 0
        ):
            scale = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
            anchor = self._x_to_frame(int(event.position().x()))
            self.zoom_requested.emit(anchor, scale)
            event.accept()
            return
        super().wheelEvent(event)

    def _seek_from_x(self, x: int):
        self.seek_requested.emit(self._x_to_frame(x, seekable=True))

    def _track_rect(self) -> QRect:
        return QRect(16, 12, max(1, self.width() - 32), 22)

    def _frame_to_x(self, frame: int) -> int:
        track = self._track_rect()
        ratio = self.viewport.frame_to_ratio(frame)
        return int(track.left() + ratio * track.width())

    def _x_to_frame(self, x: int, seekable: bool = False) -> int:
        track = self._track_rect()
        ratio = (x - track.left()) / max(track.width(), 1)
        return self.viewport.ratio_to_frame(ratio, seekable=seekable)

    def _is_frame_visible(self, frame: int) -> bool:
        return self.viewport.visible_start_frame <= frame <= self.viewport.visible_end_frame


class IntervalTrackWidget(QWidget):
    """Interval-only track with selection, creation and handle editing."""

    seek_requested = Signal(int)
    interval_created = Signal(int, int)
    interval_changed = Signal(str, int, int)
    interval_selected = Signal(str)
    thumbnail_requested = Signal(int, QPoint)
    zoom_requested = Signal(int, float)

    def __init__(self, viewport: TimelineViewport):
        super().__init__()
        self.viewport = viewport
        self.current_frame = 0
        self.intervals: List[AnnotationInterval] = []
        self.selected_interval_id: Optional[str] = None
        self.pending_start_frame: Optional[int] = None
        self._drag_mode: Optional[str] = None
        self._drag_interval_id: Optional[str] = None
        self._drag_start_frame: Optional[int] = None
        self._drag_current_frame: Optional[int] = None
        self._drag_preview: Optional[tuple[str, int, int]] = None
        self.setMouseTracking(True)
        self.setMinimumHeight(76)
        self.setStyleSheet("background: #171a1f;")

    def reset_interaction(self):
        self.selected_interval_id = None
        self.pending_start_frame = None
        self._drag_mode = None
        self._drag_interval_id = None
        self._drag_start_frame = None
        self._drag_current_frame = None
        self._drag_preview = None
        self.unsetCursor()
        self.update()

    def set_intervals(self, intervals: Iterable[AnnotationInterval]):
        self.intervals = list(intervals)
        if self.selected_interval_id and not any(
            item.id == self.selected_interval_id for item in self.intervals
        ):
            self.selected_interval_id = None
        self.update()

    def set_current_frame(self, frame: int):
        self.current_frame = self.viewport.clamp_frame(frame, seekable=True)
        self.update()

    def set_pending_start(self, frame: Optional[int]):
        self.pending_start_frame = frame
        self.update()

    def set_selected_interval(self, interval_id: Optional[str]):
        self.selected_interval_id = interval_id
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a1f"))

        track = self._track_rect()
        painter.setPen(QPen(QColor("#333841"), 1))
        painter.setBrush(QColor("#20242b"))
        painter.drawRoundedRect(track, 4, 4)

        if self.viewport.total_frames <= 0:
            painter.setPen(QColor("#8f969f"))
            painter.drawText(track, Qt.AlignmentFlag.AlignCenter, "加载视频后显示标注轨道")
            return

        painter.setPen(QPen(QColor("#2d323a"), 1))
        for fraction in (0.25, 0.5, 0.75):
            x = int(track.left() + track.width() * fraction)
            painter.drawLine(x, track.top(), x, track.bottom())

        preview_by_id = {}
        if self._drag_preview:
            interval_id, start_frame, end_frame = self._drag_preview
            preview_by_id[interval_id] = (start_frame, end_frame)

        for interval in self.intervals:
            start_frame, end_frame = preview_by_id.get(
                interval.id,
                (interval.start_frame, interval.end_frame),
            )
            self._draw_interval(painter, interval.id, start_frame, end_frame)

        if self._drag_mode == "create" and self._drag_start_frame is not None:
            start = self._drag_start_frame
            end = self._drag_current_frame if self._drag_current_frame is not None else start
            x1 = self._frame_to_x(min(start, end))
            x2 = self._frame_to_x(max(start, end))
            painter.setPen(QPen(QColor("#8bea9f"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(52, 199, 89, 90))
            painter.drawRoundedRect(
                QRect(x1, track.top() + 10, max(2, x2 - x1), track.height() - 20),
                3,
                3,
            )

        if self.pending_start_frame is not None and self._is_frame_visible(self.pending_start_frame):
            x = self._frame_to_x(self.pending_start_frame)
            painter.setPen(QPen(QColor("#f4b400"), 2))
            painter.drawLine(x, track.top() - 8, x, track.bottom() + 8)

        if self._is_frame_visible(self.current_frame):
            playhead_x = self._frame_to_x(self.current_frame)
            painter.setPen(QPen(QColor("#ff5a5f"), 2))
            painter.drawLine(playhead_x, track.top() - 12, playhead_x, track.bottom() + 12)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.viewport.total_frames <= 0:
            return

        frame = self._x_to_frame(int(event.position().x()))
        seek_frame = self.viewport.clamp_frame(frame, seekable=True)
        hit_mode, interval = self._hit_test(event.position().toPoint())
        if hit_mode in {"left", "right"} and interval is not None:
            self._drag_mode = hit_mode
            self._drag_interval_id = interval.id
            self.selected_interval_id = interval.id
            self.interval_selected.emit(interval.id)
            self.seek_requested.emit(
                interval.start_frame if hit_mode == "left" else max(0, interval.end_frame - 1)
            )
        elif hit_mode == "body" and interval is not None:
            self.selected_interval_id = interval.id
            self.interval_selected.emit(interval.id)
            self.seek_requested.emit(seek_frame)
        else:
            self._drag_mode = "create"
            self._drag_start_frame = frame
            self._drag_current_frame = frame
            self.selected_interval_id = None
            self.interval_selected.emit("")
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.viewport.total_frames <= 0:
            return
        frame = self._x_to_frame(int(event.position().x()))
        self.thumbnail_requested.emit(
            self.viewport.clamp_frame(frame, seekable=True),
            event.globalPosition().toPoint(),
        )

        if self._drag_mode == "create":
            self._drag_current_frame = frame
            self.update()
            return

        if self._drag_mode in {"left", "right"} and self._drag_interval_id:
            interval = self._interval_by_id(self._drag_interval_id)
            if interval is None:
                return
            left_bound, right_bound = self._edit_bounds(interval.id)
            start_frame = interval.start_frame
            end_frame = interval.end_frame
            if self._drag_mode == "left":
                start_frame = max(left_bound, min(frame, end_frame - 1))
            else:
                end_frame = min(right_bound, max(frame, start_frame + 1))
            self._drag_preview = (interval.id, start_frame, end_frame)
            self.update()
            return

        hit_mode, _ = self._hit_test(event.position().toPoint())
        if hit_mode in {"left", "right"}:
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._drag_mode == "create" and self._drag_start_frame is not None:
            start = self._drag_start_frame
            end = self._drag_current_frame if self._drag_current_frame is not None else start
            if abs(end - start) <= 1:
                self.seek_requested.emit(self.viewport.clamp_frame(start, seekable=True))
            else:
                self.interval_created.emit(min(start, end), max(start, end))
        elif self._drag_mode in {"left", "right"} and self._drag_preview:
            interval_id, start_frame, end_frame = self._drag_preview
            self.interval_changed.emit(interval_id, start_frame, end_frame)

        self._drag_mode = None
        self._drag_interval_id = None
        self._drag_start_frame = None
        self._drag_current_frame = None
        self._drag_preview = None
        self.unsetCursor()
        self.update()
        event.accept()

    def leaveEvent(self, event):
        self.thumbnail_requested.emit(-1, QPoint())
        super().leaveEvent(event)

    def wheelEvent(self, event):
        if (
            self.viewport.total_frames > 0
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.angleDelta().y() != 0
        ):
            scale = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
            anchor = self._x_to_frame(int(event.position().x()))
            self.zoom_requested.emit(anchor, scale)
            event.accept()
            return
        super().wheelEvent(event)

    def _draw_interval(self, painter: QPainter, interval_id: str, start_frame: int, end_frame: int):
        bounds = self._visible_interval_bounds(start_frame, end_frame)
        if bounds is None:
            return
        x1, x2, left_handle_visible, right_handle_visible = bounds
        track = self._track_rect()
        color = QColor("#34c759")
        if interval_id == self.selected_interval_id:
            color = QColor("#5ee482")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(
            QRect(x1, track.top() + 8, max(2, x2 - x1), track.height() - 16),
            3,
            3,
        )
        painter.setBrush(QColor("#d7f9df"))
        if left_handle_visible:
            painter.drawRect(self._frame_to_x(start_frame) - 2, track.top() + 5, 4, track.height() - 10)
        if right_handle_visible:
            painter.drawRect(self._frame_to_x(end_frame) - 2, track.top() + 5, 4, track.height() - 10)

    def _track_rect(self) -> QRect:
        return QRect(16, 14, max(1, self.width() - 32), 44)

    def _frame_to_x(self, frame: int) -> int:
        track = self._track_rect()
        ratio = self.viewport.frame_to_ratio(frame)
        return int(track.left() + ratio * track.width())

    def _x_to_frame(self, x: int) -> int:
        track = self._track_rect()
        ratio = (x - track.left()) / max(track.width(), 1)
        return self.viewport.ratio_to_frame(ratio)

    def _is_frame_visible(self, frame: int) -> bool:
        return self.viewport.visible_start_frame <= frame <= self.viewport.visible_end_frame

    def _visible_interval_bounds(
        self,
        start_frame: int,
        end_frame: int,
    ) -> Optional[tuple[int, int, bool, bool]]:
        visible_start = self.viewport.visible_start_frame
        visible_end = self.viewport.visible_end_frame
        if end_frame <= visible_start or start_frame >= visible_end:
            return None
        clipped_start = max(start_frame, visible_start)
        clipped_end = min(end_frame, visible_end)
        x1 = self._frame_to_x(clipped_start)
        x2 = self._frame_to_x(clipped_end)
        left_handle_visible = visible_start <= start_frame <= visible_end
        right_handle_visible = visible_start <= end_frame <= visible_end
        return x1, x2, left_handle_visible, right_handle_visible

    def _hit_test(self, point) -> tuple[Optional[str], Optional[AnnotationInterval]]:
        track = self._track_rect()
        if not (track.top() - 6 <= point.y() <= track.bottom() + 6):
            return None, None

        handle_radius = 8
        for interval in self.intervals:
            bounds = self._visible_interval_bounds(interval.start_frame, interval.end_frame)
            if bounds is None:
                continue
            x1, x2, left_handle_visible, right_handle_visible = bounds
            if left_handle_visible and abs(point.x() - self._frame_to_x(interval.start_frame)) <= handle_radius:
                return "left", interval
            if right_handle_visible and abs(point.x() - self._frame_to_x(interval.end_frame)) <= handle_radius:
                return "right", interval
            if x1 < point.x() < x2:
                return "body", interval
        return None, None

    def _interval_by_id(self, interval_id: str) -> Optional[AnnotationInterval]:
        for interval in self.intervals:
            if interval.id == interval_id:
                return interval
        return None

    def _edit_bounds(self, interval_id: str) -> tuple[int, int]:
        ordered = sorted(self.intervals, key=lambda item: (item.start_frame, item.end_frame))
        for index, interval in enumerate(ordered):
            if interval.id != interval_id:
                continue
            left = ordered[index - 1].end_frame if index > 0 else 0
            right = ordered[index + 1].start_frame if index + 1 < len(ordered) else self.viewport.total_frames
            return left, right
        return 0, self.viewport.total_frames


class TimelineWidget(QWidget):
    """Two-track timeline with shared zoom/pan viewport."""

    seek_requested = Signal(int)
    interval_created = Signal(int, int)
    interval_changed = Signal(str, int, int)
    interval_selected = Signal(str)
    thumbnail_requested = Signal(int, QPoint)

    def __init__(self):
        super().__init__()
        self.viewport = TimelineViewport()
        self.progress_track = ProgressTrackWidget(self.viewport)
        self.interval_track = IntervalTrackWidget(self.viewport)

        self.pan_left_button = QPushButton("<")
        self.pan_left_button.setFixedWidth(30)
        self.pan_left_button.setToolTip("向左移动当前显示区间")
        self.pan_left_button.clicked.connect(lambda: self._pan_visible(-1))

        self.pan_right_button = QPushButton(">")
        self.pan_right_button.setFixedWidth(30)
        self.pan_right_button.setToolTip("向右移动当前显示区间")
        self.pan_right_button.clicked.connect(lambda: self._pan_visible(1))

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self.pan_left_button)
        top_row.addWidget(self.progress_track, 1)
        top_row.addWidget(self.pan_right_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(self.interval_track)

        self.progress_track.seek_requested.connect(self.seek_requested.emit)
        self.progress_track.thumbnail_requested.connect(self.thumbnail_requested.emit)
        self.progress_track.zoom_requested.connect(self._zoom_visible)
        self.interval_track.seek_requested.connect(self.seek_requested.emit)
        self.interval_track.interval_created.connect(self.interval_created.emit)
        self.interval_track.interval_changed.connect(self.interval_changed.emit)
        self.interval_track.interval_selected.connect(self.interval_selected.emit)
        self.interval_track.thumbnail_requested.connect(self.thumbnail_requested.emit)
        self.interval_track.zoom_requested.connect(self._zoom_visible)

        self.setMinimumHeight(132)
        self.setStyleSheet("background: #171a1f;")
        self._refresh_pan_buttons()

    @property
    def selected_interval_id(self) -> Optional[str]:
        return self.interval_track.selected_interval_id

    def set_video(self, total_frames: int, fps: float):
        self.viewport.set_video(total_frames, fps)
        self.progress_track.set_current_frame(0)
        self.interval_track.set_current_frame(0)
        self.interval_track.reset_interaction()
        self._sync_tracks()

    def set_intervals(self, intervals: Iterable[AnnotationInterval]):
        self.interval_track.set_intervals(intervals)
        self._refresh_pan_buttons()

    def set_current_frame(self, frame: int):
        self.progress_track.set_current_frame(frame)
        self.interval_track.set_current_frame(frame)

    def set_pending_start(self, frame: Optional[int]):
        self.interval_track.set_pending_start(frame)

    def set_selected_interval(self, interval_id: Optional[str]):
        self.interval_track.set_selected_interval(interval_id)

    def _zoom_visible(self, anchor_frame: int, scale: float):
        self.viewport.zoom_at_frame(anchor_frame, scale)
        self._sync_tracks()

    def _pan_visible(self, direction: int):
        self.viewport.pan_by_fraction(direction)
        self._sync_tracks()

    def _sync_tracks(self):
        self.progress_track.update()
        self.interval_track.update()
        self._refresh_pan_buttons()

    def _refresh_pan_buttons(self):
        self.pan_left_button.setEnabled(self.viewport.can_pan_left())
        self.pan_right_button.setEnabled(self.viewport.can_pan_right())
