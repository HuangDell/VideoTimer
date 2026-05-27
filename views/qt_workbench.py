"""PySide6 annotation workbench for mouse video freezing labels."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import uuid4

import cv2

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from models.annotation_model import (
    DEFAULT_LABEL,
    AnnotationInterval,
    AnnotationModel,
)
from models.video_model import VideoModel
from services.annotation_export_adapter import intervals_to_time_records
from services.export_service import ExportService
from services.freezing_detection_service import (
    FreezingDetectionParams,
    FreezingDetectionService,
    FreezingInterval,
)
from utils.config import Config
from utils.time_formatter import TimeFormatter
from views.export_dialog import ExportType


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


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


class TimelineWidget(QWidget):
    """Single-track interval timeline with draggable handles."""

    seek_requested = Signal(int)
    interval_created = Signal(int, int)
    interval_changed = Signal(str, int, int)
    interval_selected = Signal(str)
    thumbnail_requested = Signal(int, QPoint)

    def __init__(self):
        super().__init__()
        self.total_frames = 0
        self.video_fps = 30.0
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
        self.setMinimumHeight(112)
        self.setStyleSheet("background: #171a1f;")

    def set_video(self, total_frames: int, fps: float):
        self.total_frames = max(0, int(total_frames))
        self.video_fps = fps if fps > 0 else 30.0
        self.current_frame = 0
        self.pending_start_frame = None
        self.selected_interval_id = None
        self.update()

    def set_intervals(self, intervals: Iterable[AnnotationInterval]):
        self.intervals = list(intervals)
        if self.selected_interval_id and not any(
            item.id == self.selected_interval_id for item in self.intervals
        ):
            self.selected_interval_id = None
        self.update()

    def set_current_frame(self, frame: int):
        self.current_frame = self._clamp_frame(frame, seekable=True)
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

        if self.total_frames <= 0:
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
            x1 = self._frame_to_x(start_frame)
            x2 = self._frame_to_x(end_frame)
            color = QColor("#34c759")
            if interval.id == self.selected_interval_id:
                color = QColor("#5ee482")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRect(x1, track.top() + 8, max(2, x2 - x1), track.height() - 16), 3, 3)
            painter.setBrush(QColor("#d7f9df"))
            painter.drawRect(x1 - 2, track.top() + 5, 4, track.height() - 10)
            painter.drawRect(x2 - 2, track.top() + 5, 4, track.height() - 10)

        if self._drag_mode == "create" and self._drag_start_frame is not None:
            start = self._drag_start_frame
            end = self._drag_current_frame if self._drag_current_frame is not None else start
            x1 = self._frame_to_x(min(start, end))
            x2 = self._frame_to_x(max(start, end))
            painter.setPen(QPen(QColor("#8bea9f"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(52, 199, 89, 90))
            painter.drawRoundedRect(QRect(x1, track.top() + 10, max(2, x2 - x1), track.height() - 20), 3, 3)

        if self.pending_start_frame is not None:
            x = self._frame_to_x(self.pending_start_frame)
            painter.setPen(QPen(QColor("#f4b400"), 2))
            painter.drawLine(x, track.top() - 8, x, track.bottom() + 8)

        playhead_x = self._frame_to_x(self.current_frame)
        painter.setPen(QPen(QColor("#ff5a5f"), 2))
        painter.drawLine(playhead_x, track.top() - 12, playhead_x, track.bottom() + 12)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.total_frames <= 0:
            return

        frame = self._x_to_frame(int(event.position().x()))
        hit_mode, interval = self._hit_test(event.position().toPoint())
        if hit_mode in {"left", "right"} and interval is not None:
            self._drag_mode = hit_mode
            self._drag_interval_id = interval.id
            self.selected_interval_id = interval.id
            self.interval_selected.emit(interval.id)
            self.seek_requested.emit(interval.start_frame if hit_mode == "left" else max(0, interval.end_frame - 1))
        elif hit_mode == "body" and interval is not None:
            self.selected_interval_id = interval.id
            self.interval_selected.emit(interval.id)
            self.seek_requested.emit(frame)
        else:
            self._drag_mode = "create"
            self._drag_start_frame = frame
            self._drag_current_frame = frame
            self.selected_interval_id = None
            self.interval_selected.emit("")
        self.update()

    def mouseMoveEvent(self, event):
        if self.total_frames > 0:
            frame = self._x_to_frame(int(event.position().x()))
            self.thumbnail_requested.emit(frame, event.globalPosition().toPoint())
        else:
            return

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
                self.seek_requested.emit(start)
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

    def leaveEvent(self, event):
        self.thumbnail_requested.emit(-1, QPoint())
        super().leaveEvent(event)

    def _track_rect(self) -> QRect:
        return QRect(16, 36, max(1, self.width() - 32), 48)

    def _frame_to_x(self, frame: int) -> int:
        track = self._track_rect()
        if self.total_frames <= 0:
            return track.left()
        ratio = self._clamp_frame(frame) / max(self.total_frames, 1)
        return int(track.left() + ratio * track.width())

    def _x_to_frame(self, x: int) -> int:
        track = self._track_rect()
        ratio = (x - track.left()) / max(track.width(), 1)
        return self._clamp_frame(round(ratio * self.total_frames))

    def _clamp_frame(self, frame: int, seekable: bool = False) -> int:
        max_frame = max(0, self.total_frames - 1) if seekable else self.total_frames
        return max(0, min(int(frame), max_frame))

    def _hit_test(self, point) -> tuple[Optional[str], Optional[AnnotationInterval]]:
        track = self._track_rect()
        handle_radius = 8
        for interval in self.intervals:
            x1 = self._frame_to_x(interval.start_frame)
            x2 = self._frame_to_x(interval.end_frame)
            if track.top() - 6 <= point.y() <= track.bottom() + 6:
                if abs(point.x() - x1) <= handle_radius:
                    return "left", interval
                if abs(point.x() - x2) <= handle_radius:
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
            right = ordered[index + 1].start_frame if index + 1 < len(ordered) else self.total_frames
            return left, right
        return 0, self.total_frames


class ThumbnailCache:
    """Small frame thumbnail cache backed by a dedicated OpenCV capture."""

    def __init__(self, max_items: int = 80):
        self.max_items = max_items
        self.capture = None
        self.total_frames = 0
        self.cache: OrderedDict[int, QPixmap] = OrderedDict()

    def load_video(self, video_path: str, total_frames: int):
        self.release()
        self.capture = cv2.VideoCapture(video_path)
        self.total_frames = max(0, int(total_frames))
        self.cache.clear()

    def get(self, frame: int, size: QSize = QSize(180, 104)) -> Optional[QPixmap]:
        if self.capture is None or not self.capture.isOpened() or self.total_frames <= 0:
            return None
        frame = max(0, min(int(frame), max(0, self.total_frames - 1)))
        if frame in self.cache:
            pixmap = self.cache.pop(frame)
            self.cache[frame] = pixmap
            return pixmap

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = self.capture.read()
        if not ok:
            return None
        pixmap = frame_to_pixmap(image).scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cache[frame] = pixmap
        while len(self.cache) > self.max_items:
            self.cache.popitem(last=False)
        return pixmap

    def release(self):
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.cache.clear()


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
    ):
        super().__init__()
        self.video_path = video_path
        self.fps = fps
        self.total_frames = total_frames
        self.params = params
        self.service = FreezingDetectionService()

    def run(self):
        try:
            intervals = self.service.detect_freezing(
                self.video_path,
                self.fps,
                self.total_frames,
                self.params,
                self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(intervals, self.video_path)


class AddIntervalCommand(QUndoCommand):
    def __init__(self, window: "QtAnnotationWorkbench", interval: AnnotationInterval):
        super().__init__("新增标注区间")
        self.window = window
        self.interval = interval

    def redo(self):
        self.window._apply_add_interval(self.interval)

    def undo(self):
        self.window._apply_delete_interval(self.interval.id)


class DeleteIntervalCommand(QUndoCommand):
    def __init__(self, window: "QtAnnotationWorkbench", interval: AnnotationInterval):
        super().__init__("删除标注区间")
        self.window = window
        self.interval = interval

    def redo(self):
        self.window._apply_delete_interval(self.interval.id)

    def undo(self):
        self.window._apply_add_interval(self.interval)


class UpdateIntervalCommand(QUndoCommand):
    def __init__(
        self,
        window: "QtAnnotationWorkbench",
        before: AnnotationInterval,
        after: AnnotationInterval,
    ):
        super().__init__("修改标注区间")
        self.window = window
        self.before = before
        self.after = after

    def redo(self):
        self.window._apply_update_interval(self.after)

    def undo(self):
        self.window._apply_update_interval(self.before)


class ReplaceIntervalsCommand(QUndoCommand):
    def __init__(
        self,
        window: "QtAnnotationWorkbench",
        before: List[AnnotationInterval],
        after: List[AnnotationInterval],
        text: str = "替换标注区间",
    ):
        super().__init__(text)
        self.window = window
        self.before = before
        self.after = after

    def redo(self):
        self.window._apply_replace_intervals(self.after)

    def undo(self):
        self.window._apply_replace_intervals(self.before)


class QtAnnotationWorkbench(QMainWindow):
    """Premiere-style single-window annotation workbench."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.time_formatter = TimeFormatter()
        self.video_model = VideoModel()
        self.annotation_model = AnnotationModel()
        self.export_service = ExportService()
        self.undo_stack = QUndoStack(self)
        self.thumbnail_cache = ThumbnailCache()
        self.current_frame = 0
        self.pending_start_frame: Optional[int] = None
        self.playing = False
        self._updating_table = False
        self._detection_thread: Optional[QThread] = None
        self._detection_worker: Optional[FreezingDetectionWorker] = None

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)
        self.undo_stack.cleanChanged.connect(self._sync_dirty_from_undo_stack)
        self.undo_stack.indexChanged.connect(lambda _index: self._sync_dirty_from_undo_stack())

        self.setWindowTitle("VideoTimer 标注工作台")
        self.resize(1500, 920)
        self._build_actions()
        self._build_ui()
        self._apply_theme()
        self._refresh_actions()

    def _build_actions(self):
        self.open_folder_action = QAction("打开文件夹", self)
        self.open_folder_action.triggered.connect(self.open_folder)

        self.save_action = QAction("保存标注", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_annotations)

        self.export_action = QAction("导出 Excel", self)
        self.export_action.triggered.connect(self.export_excel)

        self.auto_detect_action = QAction("自动检测", self)
        self.auto_detect_action.triggered.connect(self.auto_detect_freezing)

        self.delete_action = QAction("删除区间", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.triggered.connect(self.delete_selected_interval)

        self.clear_action = QAction("清空区间", self)
        self.clear_action.triggered.connect(self.clear_intervals)

        self.undo_action = self.undo_stack.createUndoAction(self, "撤销")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_stack.createRedoAction(self, "重做")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)

    def _build_ui(self):
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.open_folder_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.auto_detect_action)
        toolbar.addAction(self.export_action)
        self.addToolBar(toolbar)

        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.open_folder_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.export_action)

        edit_menu = self.menuBar().addMenu("编辑")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addAction(self.delete_action)
        edit_menu.addAction(self.clear_action)

        root_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root_splitter.addWidget(self._build_file_panel())
        root_splitter.addWidget(self._build_center_panel())
        root_splitter.addWidget(self._build_interval_panel())
        root_splitter.setStretchFactor(0, 0)
        root_splitter.setStretchFactor(1, 1)
        root_splitter.setStretchFactor(2, 0)
        root_splitter.setSizes([280, 900, 360])
        self.setCentralWidget(root_splitter)

        self.thumbnail_popup = QLabel()
        self.thumbnail_popup.setWindowFlags(Qt.WindowType.ToolTip)
        self.thumbnail_popup.setStyleSheet("QLabel { background: #111418; border: 1px solid #4a5059; padding: 4px; }")

    def _build_file_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        self.open_folder_button = QPushButton("打开文件夹")
        self.open_folder_button.clicked.connect(self.open_folder)
        layout.addWidget(self.open_folder_button)

        self.file_model = QFileSystemModel(self)
        self.file_model.setRootPath(str(Path.cwd()))
        filters = [f"*{suffix}" for suffix in sorted(VIDEO_EXTENSIONS)]
        filters.extend(f"*{suffix.upper()}" for suffix in sorted(VIDEO_EXTENSIONS))
        self.file_model.setNameFilters(filters)
        self.file_model.setNameFilterDisables(False)

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(Path.cwd())))
        self.file_tree.setHeaderHidden(True)
        for column in (1, 2, 3):
            self.file_tree.hideColumn(column)
        self.file_tree.doubleClicked.connect(self._on_file_double_clicked)
        layout.addWidget(self.file_tree, 1)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        self.video_canvas = VideoCanvas()
        layout.addWidget(self.video_canvas, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setText("播放")
        self.play_button.clicked.connect(self.toggle_playback)
        controls.addWidget(self.play_button)

        self.stop_button = QPushButton("重置")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_video)
        controls.addWidget(self.stop_button)

        self.fullscreen_button = QPushButton("全屏")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        controls.addWidget(self.fullscreen_button)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.8x", "1.0x", "1.5x", "2.0x", "3.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        controls.addWidget(self.speed_combo)

        controls.addStretch(1)
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        self.video_info_label = QLabel("未加载视频")
        layout.addWidget(self.video_info_label)

        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.seek_to_frame)
        self.timeline.interval_created.connect(self._push_add_interval)
        self.timeline.interval_changed.connect(self._push_update_interval)
        self.timeline.interval_selected.connect(self._select_interval)
        self.timeline.thumbnail_requested.connect(self._show_thumbnail)
        layout.addWidget(self.timeline)

        return panel

    def _build_interval_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)

        button_row = QHBoxLayout()
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_selected_interval)
        button_row.addWidget(self.delete_button)

        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_intervals)
        button_row.addWidget(self.clear_button)
        layout.addLayout(button_row)

        self.interval_table = QTableWidget(0, 3)
        self.interval_table.setHorizontalHeaderLabels(["start_time", "end_time", "duration"])
        self.interval_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.interval_table.verticalHeader().setVisible(False)
        self.interval_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.interval_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.interval_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.interval_table.itemClicked.connect(self._on_table_item_clicked)
        self.interval_table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.interval_table, 1)

        self.stats_label = QLabel("区间数: 0")
        layout.addWidget(self.stats_label)
        return panel

    def _apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #171a1f; color: #e8eaed; }
            QMenuBar, QMenu, QToolBar { background: #20242b; color: #e8eaed; }
            QPushButton, QComboBox { background: #2a2f37; color: #f1f3f4; border: 1px solid #444b55; padding: 5px 8px; }
            QPushButton:hover, QComboBox:hover { background: #353b45; }
            QTableWidget, QTreeView { background: #111418; alternate-background-color: #171a1f; color: #e8eaed; gridline-color: #30363f; border: 1px solid #30363f; }
            QHeaderView::section { background: #20242b; color: #cfd4dc; border: 0; padding: 6px; }
            QLabel { color: #e8eaed; }
            """
        )

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹", str(Path.cwd()))
        if not folder:
            return
        self.file_model.setRootPath(folder)
        self.file_tree.setRootIndex(self.file_model.index(folder))

    def _on_file_double_clicked(self, index: QModelIndex):
        file_path = self.file_model.filePath(index)
        path = Path(file_path)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            self.load_video(str(path))

    def load_video(self, file_path: str):
        if not self._confirm_save_if_dirty():
            return

        self.stop_video()
        self.thumbnail_popup.hide()
        self.thumbnail_cache.release()
        self.video_model.release()
        if not self.video_model.load_video(file_path):
            QMessageBox.critical(self, "错误", "无法打开视频文件")
            return

        self.current_frame = 0
        self.annotation_model.set_video_context(
            file_path,
            self.video_model.video_fps,
            self.video_model.total_frames,
        )

        loaded_sidecar = False
        try:
            loaded_sidecar = self.annotation_model.load_sidecar(file_path)
        except Exception as exc:
            self.annotation_model.set_video_context(
                file_path,
                self.video_model.video_fps,
                self.video_model.total_frames,
            )
            QMessageBox.warning(self, "标注加载失败", f"标注文件无法加载，已使用空标注。\n\n{exc}")

        self.thumbnail_cache.load_video(file_path, self.video_model.total_frames)
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self.pending_start_frame = None
        self.timeline.set_video(self.video_model.total_frames, self.video_model.video_fps)
        self.timeline.set_pending_start(None)
        self._refresh_all_views()
        self._render_current_frame()

        duration = self.time_formatter.format_time(self.video_model.duration)
        self.video_info_label.setText(
            f"{Path(file_path).name} | {duration} | "
            f"{self.video_model.total_frames} frames | {self.video_model.video_fps:.2f} fps"
        )
        self.statusBar().showMessage(
            "已加载标注文件" if loaded_sidecar else "已加载视频，未发现同名标注文件",
            5000,
        )
        self._refresh_actions()

    def toggle_playback(self):
        if not self.video_model.video_capture:
            return
        if self.playing:
            self._pause_playback()
            return
        self.playing = True
        self.play_button.setText("暂停")
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self._restart_play_timer()

    def stop_video(self):
        self._pause_playback()
        if self.video_model.video_capture:
            self.seek_to_frame(0)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def seek_to_frame(self, frame: int):
        if not self.video_model.video_capture:
            return
        self.current_frame = max(0, min(int(frame), max(0, self.video_model.total_frames - 1)))
        self.video_model.current_frame = self.current_frame
        self._render_current_frame()

    def _advance_playback(self):
        if not self.playing or not self.video_model.video_capture:
            return
        if self.current_frame >= self.video_model.total_frames - 1:
            self._pause_playback()
            self.current_frame = max(0, self.video_model.total_frames - 1)
            return
        self.current_frame += 1
        self.video_model.current_frame = self.current_frame
        self._render_current_frame()
        if self.current_frame >= self.video_model.total_frames - 1:
            self._pause_playback()

    def _render_current_frame(self):
        capture = self.video_model.video_capture
        if not capture:
            return
        capture.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ok, frame = capture.read()
        if not ok:
            self._pause_playback()
            return
        self.video_canvas.set_frame(frame)
        self.video_model.current_frame = self.current_frame
        self.timeline.set_current_frame(self.current_frame)
        self._update_time_label()

    def _pause_playback(self):
        self.playing = False
        self.play_timer.stop()
        if hasattr(self, "play_button"):
            self.play_button.setText("播放")
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def _restart_play_timer(self):
        speed = float(self.speed_combo.currentText().rstrip("x"))
        delay = max(1, int(1000 / max(self.video_model.video_fps * speed, 1.0)))
        self.play_timer.start(delay)

    def _on_speed_changed(self):
        if self.playing:
            self._restart_play_timer()

    def save_annotations(self) -> bool:
        if not self.video_model.video_path:
            return True
        try:
            path = self.annotation_model.save_sidecar(self.video_model.video_path)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self.undo_stack.setClean()
        self.statusBar().showMessage(f"标注已保存: {path}", 5000)
        self._refresh_actions()
        return True

    def export_excel(self):
        if not self.video_model.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return
        if not self.annotation_model.intervals:
            QMessageBox.warning(self, "警告", "没有标注区间可导出")
            return

        labels = ["Looming", "FC (Training)", "OFC", "Test"]
        choice, ok = QInputDialog.getItem(self, "选择导出类型", "导出类型", labels, 0, False)
        if not ok:
            return
        export_type = {
            "Looming": ExportType.LOOMING,
            "FC (Training)": ExportType.TRAINING,
            "OFC": ExportType.OFC,
            "Test": ExportType.TEST,
        }[choice]

        default_name = f"{Path(self.video_model.video_path).stem}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 Excel 文件",
            str(Path(self.video_model.video_path).with_name(default_name)),
            "Excel files (*.xlsx);;All files (*.*)",
        )
        if not file_path:
            return

        records = intervals_to_time_records(
            self.annotation_model.intervals,
            self.video_model.video_fps,
        )
        if self.export_service.export("excel", records, self.video_model, file_path, export_type):
            QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")
        else:
            QMessageBox.critical(self, "错误", "导出失败")

    def auto_detect_freezing(self):
        if not self.video_model.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return
        if self._detection_thread is not None:
            return

        self._pause_playback()
        params = FreezingDetectionParams(
            sample_rate=float(self.config.get("freezing_sample_rate", 10.0)),
            analysis_width=int(self.config.get("freezing_analysis_width", 320)),
            pixel_diff_threshold=int(self.config.get("freezing_pixel_diff_threshold", 25)),
            motion_threshold=float(self.config.get("freezing_motion_threshold", 0.0004)),
            min_freeze_duration=float(self.config.get("freezing_min_duration", 0.5)),
            merge_gap=float(self.config.get("freezing_merge_gap", 0.3)),
            min_non_freeze_gap=float(self.config.get("freezing_min_non_freeze_gap", 0.2)),
            smoothing_window=float(self.config.get("freezing_smoothing_window", 0.3)),
        )

        self._detection_thread = QThread(self)
        self._detection_worker = FreezingDetectionWorker(
            self.video_model.video_path,
            self.video_model.video_fps,
            self.video_model.total_frames,
            params,
        )
        self._detection_worker.moveToThread(self._detection_thread)
        self._detection_thread.started.connect(self._detection_worker.run)
        self._detection_worker.progress.connect(self._on_detection_progress)
        self._detection_worker.finished.connect(self._on_detection_finished)
        self._detection_worker.failed.connect(self._on_detection_failed)
        self._detection_worker.finished.connect(self._detection_thread.quit)
        self._detection_worker.failed.connect(self._detection_thread.quit)
        self._detection_thread.finished.connect(self._detection_worker.deleteLater)
        self._detection_thread.finished.connect(self._on_detection_thread_finished)
        self.auto_detect_action.setEnabled(False)
        self.statusBar().showMessage("自动检测中: 0%")
        self._detection_thread.start()

    def delete_selected_interval(self):
        interval_id = self._current_table_interval_id()
        if not interval_id and self.timeline.selected_interval_id:
            interval_id = self.timeline.selected_interval_id
        if not interval_id:
            return
        interval = self.annotation_model.get_interval(interval_id)
        if interval is None:
            return
        self.undo_stack.push(DeleteIntervalCommand(self, interval))

    def clear_intervals(self):
        if not self.annotation_model.intervals:
            return
        answer = QMessageBox.question(self, "清空标注", "确认清空当前视频的所有标注区间？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.undo_stack.push(
            ReplaceIntervalsCommand(
                self,
                self.annotation_model.intervals,
                [],
                "清空标注区间",
            )
        )

    def _push_add_interval(self, start_frame: int, end_frame: int):
        if not self.video_model.video_path:
            return
        start_frame = self.annotation_model.clamp_frame(start_frame)
        end_frame = self.annotation_model.clamp_frame(end_frame)
        interval = AnnotationInterval(
            id=str(uuid4()),
            label=DEFAULT_LABEL,
            start_frame=start_frame,
            end_frame=end_frame,
        )
        try:
            self.annotation_model.validate_interval_data(
                interval.start_frame,
                interval.end_frame,
                interval.label,
                interval.id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "无法新增区间", str(exc))
            self._refresh_all_views()
            return
        self.undo_stack.push(AddIntervalCommand(self, interval))
        self._select_interval(interval.id)

    def _push_update_interval(self, interval_id: str, start_frame: int, end_frame: int):
        before = self.annotation_model.get_interval(interval_id)
        if before is None:
            return
        start_frame = self.annotation_model.clamp_frame(start_frame)
        end_frame = self.annotation_model.clamp_frame(end_frame)
        if before.start_frame == start_frame and before.end_frame == end_frame:
            return
        after = AnnotationInterval(
            id=before.id,
            label=before.label,
            start_frame=start_frame,
            end_frame=end_frame,
        )
        try:
            self.annotation_model.validate_interval_data(
                after.start_frame,
                after.end_frame,
                after.label,
                after.id,
                ignore_id=after.id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "无法修改区间", str(exc))
            self._refresh_all_views()
            return
        self.undo_stack.push(UpdateIntervalCommand(self, before, after))
        self._select_interval(after.id)

    def _apply_add_interval(self, interval: AnnotationInterval):
        self.annotation_model.add_interval(
            interval.start_frame,
            interval.end_frame,
            interval.label,
            interval.id,
        )
        self._refresh_all_views()

    def _apply_delete_interval(self, interval_id: str):
        if self.annotation_model.get_interval(interval_id) is not None:
            self.annotation_model.delete_interval(interval_id)
        self._refresh_all_views()

    def _apply_update_interval(self, interval: AnnotationInterval):
        self.annotation_model.update_interval(
            interval.id,
            interval.start_frame,
            interval.end_frame,
            interval.label,
        )
        self._refresh_all_views()

    def _apply_replace_intervals(self, intervals: List[AnnotationInterval]):
        self.annotation_model.replace_intervals(intervals)
        self._refresh_all_views()

    def _refresh_all_views(self):
        self.timeline.set_intervals(self.annotation_model.intervals)
        self.timeline.set_pending_start(self.pending_start_frame)
        self._refresh_interval_table()
        self._update_time_label()
        self._refresh_actions()

    def _refresh_interval_table(self):
        self._updating_table = True
        intervals = self.annotation_model.intervals
        self.interval_table.setRowCount(len(intervals))
        for row, interval in enumerate(intervals):
            start_seconds = self.annotation_model.frame_to_seconds(interval.start_frame)
            end_seconds = self.annotation_model.frame_to_seconds(interval.end_frame)
            duration_seconds = max(0.0, end_seconds - start_seconds)
            values = [
                self.time_formatter.format_time(start_seconds),
                self.time_formatter.format_time(end_seconds),
                self.time_formatter.format_time(duration_seconds),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, interval.id)
                if column == 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.interval_table.setItem(row, column, item)
        self._updating_table = False
        total_duration = sum(
            self.annotation_model.frame_to_seconds(item.duration_frames)
            for item in intervals
        )
        self.stats_label.setText(
            f"区间数: {len(intervals)} | 总时长: {self.time_formatter.format_time(total_duration)}"
        )

    def _update_time_label(self):
        current = self.time_formatter.format_time(
            self.annotation_model.frame_to_seconds(self.current_frame)
            if self.video_model.video_path
            else 0
        )
        total = self.time_formatter.format_time(self.video_model.duration if self.video_model.video_path else 0)
        self.time_label.setText(f"{current} / {total}")

    def _on_table_item_clicked(self, item: QTableWidgetItem):
        if self._updating_table:
            return
        interval_id = item.data(Qt.ItemDataRole.UserRole)
        interval = self.annotation_model.get_interval(interval_id)
        if interval is None:
            return
        self._select_interval(interval_id)
        if item.column() == 0:
            self.seek_to_frame(interval.start_frame)
        elif item.column() == 1:
            self.seek_to_frame(max(0, interval.end_frame - 1))

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if self._updating_table or item.column() not in (0, 1):
            return
        interval_id = item.data(Qt.ItemDataRole.UserRole)
        interval = self.annotation_model.get_interval(interval_id)
        if interval is None:
            return
        try:
            frame = self.annotation_model.seconds_to_frame(parse_time_text(item.text()))
        except ValueError as exc:
            QMessageBox.warning(self, "时间格式错误", str(exc))
            self._refresh_interval_table()
            return
        if item.column() == 0:
            self._push_update_interval(interval.id, frame, interval.end_frame)
        else:
            self._push_update_interval(interval.id, interval.start_frame, frame)

    def _select_interval(self, interval_id: Optional[str]):
        interval_id = interval_id or None
        self.timeline.set_selected_interval(interval_id)
        if interval_id is None:
            self.interval_table.clearSelection()
            return
        for row in range(self.interval_table.rowCount()):
            item = self.interval_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == interval_id:
                self.interval_table.selectRow(row)
                return

    def _current_table_interval_id(self) -> Optional[str]:
        row = self.interval_table.currentRow()
        if row < 0:
            return None
        item = self.interval_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _show_thumbnail(self, frame: int, global_pos: QPoint):
        if frame < 0:
            self.thumbnail_popup.hide()
            return
        pixmap = self.thumbnail_cache.get(frame)
        if pixmap is None:
            self.thumbnail_popup.hide()
            return
        self.thumbnail_popup.setPixmap(pixmap)
        self.thumbnail_popup.adjustSize()
        self.thumbnail_popup.move(global_pos + QPoint(16, -self.thumbnail_popup.height() - 12))
        self.thumbnail_popup.show()

    def _on_detection_progress(self, progress: float):
        self.statusBar().showMessage(f"自动检测中: {progress * 100:.0f}%")

    def _on_detection_finished(self, intervals: List[FreezingInterval], source_video_path: str):
        if self.video_model.video_path != source_video_path:
            QMessageBox.information(self, "自动检测完成", "视频已切换，旧检测结果已丢弃。")
            return
        if not intervals:
            QMessageBox.information(self, "自动检测完成", "未检测到符合条件的 freezing 区间。")
            return

        total_duration = sum(item.duration for item in intervals)
        message = (
            f"检测到 {len(intervals)} 个候选区间，"
            f"总时长 {total_duration:.3f} 秒。\n\n是否覆盖导入当前标注？"
        )
        if QMessageBox.question(self, "自动检测完成", message) != QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("检测结果未导入", 5000)
            return

        annotations = [
            AnnotationInterval(
                id=str(uuid4()),
                label=DEFAULT_LABEL,
                start_frame=item.start_frame,
                end_frame=item.end_frame,
            )
            for item in intervals
            if item.end_frame > item.start_frame
        ]
        if not annotations:
            QMessageBox.information(self, "自动检测完成", "检测结果没有可导入的有效区间。")
            return
        validation_model = AnnotationModel()
        validation_model.set_video_context(
            self.video_model.video_path,
            self.video_model.video_fps,
            self.video_model.total_frames,
        )
        try:
            validation_model.replace_intervals(annotations)
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        imported = validation_model.intervals
        before = self.annotation_model.intervals

        self.undo_stack.push(
            ReplaceIntervalsCommand(
                self,
                before,
                imported,
                "导入自动检测区间",
            )
        )
        self.statusBar().showMessage(f"已导入 {len(imported)} 个候选区间", 5000)

    def _on_detection_failed(self, message: str):
        QMessageBox.critical(self, "自动检测失败", message)

    def _on_detection_thread_finished(self):
        self.auto_detect_action.setEnabled(True)
        self._detection_worker = None
        if self._detection_thread is not None:
            self._detection_thread.deleteLater()
        self._detection_thread = None
        self._refresh_actions()

    def _confirm_save_if_dirty(self) -> bool:
        if not self._has_unsaved_changes():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("切换视频")
        box.setText("当前视频的标注尚未保存。")
        box.setInformativeText("是否保存后再切换？")
        save_button = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("放弃", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_button:
            return self.save_annotations()
        if clicked == discard_button:
            return True
        if clicked == cancel_button:
            return False
        return False

    def _refresh_actions(self):
        has_video = bool(self.video_model.video_path)
        self.save_action.setEnabled(has_video and self._has_unsaved_changes())
        self.export_action.setEnabled(has_video and self.annotation_model.count > 0)
        self.delete_action.setEnabled(has_video and self.annotation_model.count > 0)
        self.clear_action.setEnabled(has_video and self.annotation_model.count > 0)
        if self._detection_thread is None:
            self.auto_detect_action.setEnabled(has_video)

    def _has_unsaved_changes(self) -> bool:
        return self.annotation_model.dirty or not self.undo_stack.isClean()

    def _sync_dirty_from_undo_stack(self):
        if self.video_model.video_path:
            self.annotation_model.dirty = not self.undo_stack.isClean()
        self._refresh_actions()

    def keyPressEvent(self, event):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_interval()
            return
        if (
            event.key() == Qt.Key.Key_Z
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
            and self.video_model.video_path
        ):
            self._toggle_pending_interval_at_current_frame()
            return
        super().keyPressEvent(event)

    def _toggle_pending_interval_at_current_frame(self):
        if self.pending_start_frame is None:
            self.pending_start_frame = self.current_frame
            self.timeline.set_pending_start(self.pending_start_frame)
            self.statusBar().showMessage(
                f"已设置起点: {self.time_formatter.format_time(self.annotation_model.frame_to_seconds(self.current_frame))}",
                3000,
            )
            return

        start = self.pending_start_frame
        end = self.current_frame
        self.pending_start_frame = None
        self.timeline.set_pending_start(None)
        if start == end:
            QMessageBox.warning(self, "无法新增区间", "区间结束时间必须晚于开始时间")
            return
        self._push_add_interval(min(start, end), max(start, end))

    def closeEvent(self, event):
        if self._confirm_save_if_dirty():
            self.thumbnail_cache.release()
            self.video_model.release()
            event.accept()
        else:
            event.ignore()


def parse_time_text(text: str) -> float:
    parts = text.strip().split(":")
    if len(parts) == 1:
        try:
            return max(0.0, float(parts[0]))
        except ValueError as exc:
            raise ValueError("请输入秒数或 HH:MM:SS.mmm") from exc
    if len(parts) != 3:
        raise ValueError("请输入 HH:MM:SS.mmm")
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError as exc:
        raise ValueError("请输入 HH:MM:SS.mmm") from exc
    if hours < 0 or minutes < 0 or seconds < 0:
        raise ValueError("时间不能为负数")
    return hours * 3600 + minutes * 60 + seconds


def run_qt_workbench():
    app = QApplication.instance() or QApplication([])
    window = QtAnnotationWorkbench()
    window.show()
    return app.exec()
