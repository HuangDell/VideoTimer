"""Main PySide6 annotation workbench."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import cv2
from PySide6.QtCore import QEvent, QPoint, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QKeySequence, QUndoGroup, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStyle,
    QTableWidgetItem,
    QToolBar,
    QWidget,
)

from models.annotation_model import DEFAULT_LABEL, AnnotationInterval, AnnotationModel
from models.export_types import ExportType
from models.video_model import VideoModel
from services.annotation_export_adapter import intervals_to_time_records
from services.export_service import ExportService
from services.freezing_detection_service import FreezingDetectionParams, FreezingInterval
from services.video_crop_service import (
    CROP_LOWER,
    CROP_UPPER,
    apply_horizontal_crop,
    clamp_split_ratio,
    logical_split_video_path,
)
from utils.config import Config
from utils.time_formatter import TimeFormatter
from views.qt.commands import (
    AddIntervalCommand,
    DeleteIntervalCommand,
    ReplaceIntervalsCommand,
    UpdateIntervalCommand,
)
from views.qt.session import VideoSession, session_metadata, session_metadata_values
from views.qt.thumbnail_cache import ThumbnailCache
from views.qt.time_parsing import parse_time_text
from views.qt.widgets.file_panel import FilePanel
from views.qt.widgets.interval_panel import IntervalPanel
from views.qt.widgets.player_panel import PlayerPanel
from views.qt.widgets.split_preview import SplitPreviewDialog
from views.qt.widgets.video_canvas import VideoCanvas
from views.qt.workers import FreezingDetectionWorker


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


class QtAnnotationWorkbench(QMainWindow):
    """Premiere-style single-window annotation workbench."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.time_formatter = TimeFormatter()
        self.video_model = VideoModel()
        self.annotation_model = AnnotationModel()
        self.export_service = ExportService()
        self.undo_group = QUndoGroup(self)
        self.undo_stack = QUndoStack(self)
        self.thumbnail_cache = ThumbnailCache()
        self.video_sessions: List[VideoSession] = []
        self.current_session_index = -1
        self.current_frame = 0
        self.pending_start_frame: Optional[int] = None
        self.playing = False
        self._updating_table = False
        self._detection_thread: Optional[QThread] = None
        self._detection_worker: Optional[FreezingDetectionWorker] = None

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advance_playback)

        self.setWindowTitle("VideoTimer 标注工作台")
        self.resize(1500, 920)
        self._build_actions()
        self._build_ui()
        self._apply_theme()
        self._refresh_actions()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

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

        self.split_action = QAction("拆分上下鼠", self)
        self.split_action.triggered.connect(self.split_top_bottom_mice)

        self.delete_action = QAction("删除区间", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.triggered.connect(self.delete_selected_interval)

        self.clear_action = QAction("清空区间", self)
        self.clear_action.triggered.connect(self.clear_intervals)

        self.undo_action = self.undo_group.createUndoAction(self, "撤销")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_group.createRedoAction(self, "重做")
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
        toolbar.addAction(self.split_action)
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
        self.file_panel = FilePanel(VIDEO_EXTENSIONS, Path.cwd(), self)
        self.file_panel.folder_requested.connect(self.open_folder)
        self.file_panel.video_selected.connect(self.load_video)
        return self.file_panel

    def _build_center_panel(self) -> QWidget:
        self.player_panel = PlayerPanel(self)
        self.video_tabs = self.player_panel.video_tabs
        self.video_canvas = self.player_panel.video_canvas
        self.play_button = self.player_panel.play_button
        self.speed_combo = self.player_panel.speed_combo
        self.time_label = self.player_panel.time_label
        self.video_info_label = self.player_panel.video_info_label
        self.timeline = self.player_panel.timeline

        self.player_panel.play_requested.connect(self.toggle_playback)
        self.player_panel.stop_requested.connect(self.stop_video)
        self.player_panel.fullscreen_requested.connect(self.toggle_fullscreen)
        self.player_panel.speed_changed.connect(self._on_speed_changed)
        self.player_panel.seek_requested.connect(self.seek_to_frame)
        self.player_panel.interval_created.connect(self._push_add_interval)
        self.player_panel.interval_changed.connect(self._push_update_interval)
        self.player_panel.interval_selected.connect(self._select_interval)
        self.player_panel.thumbnail_requested.connect(self._show_thumbnail)
        self.video_tabs.currentChanged.connect(self._on_video_tab_changed)
        return self.player_panel

    def _build_interval_panel(self) -> QWidget:
        self.interval_panel = IntervalPanel(self)
        self.interval_table = self.interval_panel.interval_table
        self.stats_label = self.interval_panel.stats_label

        self.interval_panel.delete_requested.connect(self.delete_selected_interval)
        self.interval_panel.clear_requested.connect(self.clear_intervals)
        self.interval_panel.item_clicked.connect(self._on_table_item_clicked)
        self.interval_panel.item_changed.connect(self._on_table_item_changed)
        return self.interval_panel

    def _apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #171a1f; color: #e8eaed; }
            QMenuBar, QMenu, QToolBar { background: #20242b; color: #e8eaed; }
            QPushButton, QComboBox { background: #2a2f37; color: #f1f3f4; border: 1px solid #444b55; padding: 5px 8px; }
            QPushButton:hover, QComboBox:hover { background: #353b45; }
            QTabBar::tab { background: #20242b; color: #ffffff; border: 1px solid #444b55; padding: 6px 10px; }
            QTabBar::tab:selected { background: #2a2f37; color: #ffffff; }
            QTableWidget, QTreeView { background: #111418; alternate-background-color: #171a1f; color: #e8eaed; gridline-color: #30363f; border: 1px solid #30363f; }
            QHeaderView::section { background: #20242b; color: #cfd4dc; border: 0; padding: 6px; }
            QLabel { color: #e8eaed; }
            """
        )

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹", str(Path.cwd()))
        if not folder:
            return
        self.file_panel.set_root_folder(folder)

    def _current_session(self) -> Optional[VideoSession]:
        if 0 <= self.current_session_index < len(self.video_sessions):
            return self.video_sessions[self.current_session_index]
        return None

    def _has_current_session(self) -> bool:
        return self._current_session() is not None

    def _session_metadata_values(
        self,
        source_path: str,
        logical_path: str,
        crop_role: Optional[str],
        split_ratio: Optional[float],
    ) -> dict:
        return session_metadata_values(source_path, logical_path, crop_role, split_ratio)

    def _session_metadata(self, session: VideoSession) -> dict:
        return session_metadata(session)

    def _create_video_session(
        self,
        source_path: str,
        logical_path: str,
        title: str,
        crop_role: Optional[str] = None,
        split_ratio: Optional[float] = None,
    ) -> VideoSession:
        annotation_model = AnnotationModel()
        annotation_model.set_video_context(
            logical_path,
            self.video_model.video_fps,
            self.video_model.total_frames,
            self._session_metadata_values(source_path, logical_path, crop_role, split_ratio),
        )

        loaded_sidecar = False
        try:
            loaded_sidecar = annotation_model.load_sidecar(logical_path)
        except Exception as exc:
            annotation_model.set_video_context(
                logical_path,
                self.video_model.video_fps,
                self.video_model.total_frames,
                self._session_metadata_values(source_path, logical_path, crop_role, split_ratio),
            )
            QMessageBox.warning(self, "标注加载失败", f"标注文件无法加载，已使用空标注。\n\n{exc}")

        undo_stack = QUndoStack(self)
        undo_stack.cleanChanged.connect(self._sync_dirty_from_undo_stack)
        undo_stack.indexChanged.connect(lambda _index: self._sync_dirty_from_undo_stack())
        undo_stack.setClean()

        return VideoSession(
            source_path=source_path,
            logical_path=logical_path,
            title=title,
            canvas=VideoCanvas(),
            annotation_model=annotation_model,
            undo_stack=undo_stack,
            crop_role=crop_role,
            split_ratio=split_ratio,
            loaded_sidecar=loaded_sidecar,
        )

    def _install_video_sessions(self, sessions: List[VideoSession], active_index: int = 0):
        self.video_tabs.blockSignals(True)
        for session in self.video_sessions:
            self.undo_group.removeStack(session.undo_stack)
        while self.video_tabs.count():
            self.video_tabs.removeTab(0)

        self.video_sessions = sessions
        for session in self.video_sessions:
            self.undo_group.addStack(session.undo_stack)
            self.video_tabs.addTab(session.canvas, session.title)

        self.current_session_index = -1
        if self.video_sessions:
            active_index = max(0, min(active_index, len(self.video_sessions) - 1))
            self.video_tabs.setCurrentIndex(active_index)
        self.video_tabs.blockSignals(False)
        self._activate_video_session(active_index if self.video_sessions else -1)

    def _activate_video_session(self, index: int):
        if not (0 <= index < len(self.video_sessions)):
            self.current_session_index = -1
            self.annotation_model = AnnotationModel()
            self.undo_stack = QUndoStack(self)
            self.undo_group.setActiveStack(None)
            return

        self.current_session_index = index
        session = self.video_sessions[index]
        self.annotation_model = session.annotation_model
        self.undo_stack = session.undo_stack
        self.video_canvas = session.canvas
        self.undo_group.setActiveStack(session.undo_stack)
        self.pending_start_frame = None
        self.timeline.set_pending_start(None)
        self._refresh_all_views()
        self._render_current_frame()
        self._update_video_info_label()

    def _on_video_tab_changed(self, index: int):
        if 0 <= index < len(self.video_sessions):
            self._activate_video_session(index)

    def _update_video_info_label(self):
        session = self._current_session()
        if not session:
            self.video_info_label.setText("未加载视频")
            return
        duration = self.time_formatter.format_time(self.video_model.duration)
        crop_text = ""
        if session.crop_role == CROP_UPPER:
            crop_text = " | 上半区 _1"
        elif session.crop_role == CROP_LOWER:
            crop_text = " | 下半区 _2"
        self.video_info_label.setText(
            f"{Path(session.logical_path).name} | {duration} | "
            f"{self.video_model.total_frames} frames | {self.video_model.video_fps:.2f} fps"
            f"{crop_text}"
        )

    def _export_video_model_for_current_session(self) -> VideoModel:
        session = self._current_session()
        export_model = VideoModel()
        export_model.video_path = session.logical_path if session else self.video_model.video_path
        export_model.video_fps = self.video_model.video_fps
        export_model.total_frames = self.video_model.total_frames
        export_model.current_frame = self.current_frame
        return export_model

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
        session = self._create_video_session(file_path, file_path, Path(file_path).name)

        self.thumbnail_cache.load_video(file_path, self.video_model.total_frames)
        self._install_video_sessions([session])
        self.pending_start_frame = None
        self.timeline.set_video(self.video_model.total_frames, self.video_model.video_fps)
        self.timeline.set_pending_start(None)
        self._refresh_all_views()
        self._render_current_frame()

        self._update_video_info_label()
        self.statusBar().showMessage(
            "已加载标注文件" if session.loaded_sidecar else "已加载视频，未发现同名标注文件",
            5000,
        )
        self._refresh_actions()

    def split_top_bottom_mice(self):
        if not self.video_model.video_capture or not self.video_model.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return

        is_existing_split = (
            len(self.video_sessions) == 2
            and {session.crop_role for session in self.video_sessions} == {CROP_UPPER, CROP_LOWER}
        )
        if not is_existing_split and self._has_unsaved_changes():
            if not self._confirm_save_if_dirty():
                return

        capture = self.video_model.video_capture
        capture.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ok, frame = capture.read()
        if not ok:
            QMessageBox.warning(self, "提示", "无法读取当前帧用于裁剪预览")
            return

        current_ratio = 0.5
        if is_existing_split and self.video_sessions[0].split_ratio is not None:
            current_ratio = self.video_sessions[0].split_ratio

        dialog = SplitPreviewDialog(frame, current_ratio, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        split_ratio = clamp_split_ratio(dialog.split_ratio)
        source_path = self.video_model.video_path

        if is_existing_split:
            for session in self.video_sessions:
                session.split_ratio = split_ratio
                session.annotation_model.update_video_metadata(self._session_metadata(session))
                session.metadata_dirty = True
            self.thumbnail_cache.cache.clear()
            self._refresh_all_views()
            self._render_current_frame()
            self.statusBar().showMessage("已更新上下鼠分割线，请保存各标签页标注", 5000)
            return

        upper_path = logical_split_video_path(source_path, 1)
        lower_path = logical_split_video_path(source_path, 2)
        sessions = [
            self._create_video_session(
                source_path,
                upper_path,
                Path(upper_path).name,
                CROP_UPPER,
                split_ratio,
            ),
            self._create_video_session(
                source_path,
                lower_path,
                Path(lower_path).name,
                CROP_LOWER,
                split_ratio,
            ),
        ]
        self._install_video_sessions(sessions)
        self.thumbnail_cache.cache.clear()
        loaded_count = sum(1 for session in sessions if session.loaded_sidecar)
        self.statusBar().showMessage(
            f"已创建上下鼠标签页，加载了 {loaded_count} 个已有标注文件",
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
        self._render_current_frame(seek=False)
        if self.current_frame >= self.video_model.total_frames - 1:
            self._pause_playback()

    def _render_current_frame(self, seek: bool = True):
        capture = self.video_model.video_capture
        if not capture:
            return
        if seek:
            capture.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        ok, frame = capture.read()
        if not ok:
            self._pause_playback()
            return
        session = self._current_session()
        if session:
            frame = apply_horizontal_crop(frame, session.crop_role, session.split_ratio)
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
        speed = max(float(self.speed_combo.currentText().rstrip("x")), 0.01)
        delay = max(1, int(1000 / max(self.video_model.video_fps * speed, 1.0)))
        self.play_timer.start(delay)

    def _on_speed_changed(self):
        if self.playing:
            self._restart_play_timer()

    def save_annotations(self) -> bool:
        session = self._current_session()
        if not session:
            return True
        try:
            path = self._save_session_annotations(session)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self.statusBar().showMessage(f"标注已保存: {path}", 5000)
        self._refresh_actions()
        return True

    def _save_session_annotations(self, session: VideoSession) -> Path:
        session.annotation_model.update_video_metadata(self._session_metadata(session), dirty=False)
        path = session.annotation_model.save_sidecar(session.logical_path)
        session.undo_stack.setClean()
        session.metadata_dirty = False
        session.annotation_model.dirty = False
        return path

    def _save_dirty_sessions(self) -> bool:
        try:
            for session in self.video_sessions:
                if session.annotation_model.dirty or session.metadata_dirty or not session.undo_stack.isClean():
                    self._save_session_annotations(session)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False
        self._refresh_actions()
        return True

    def export_excel(self):
        session = self._current_session()
        if not session:
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

        default_name = f"{Path(session.logical_path).stem}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 Excel 文件",
            str(Path(session.logical_path).with_name(default_name)),
            "Excel files (*.xlsx);;All files (*.*)",
        )
        if not file_path:
            return

        records = intervals_to_time_records(
            self.annotation_model.intervals,
            self.video_model.video_fps,
        )
        export_model = self._export_video_model_for_current_session()
        if self.export_service.export("excel", records, export_model, file_path, export_type):
            QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")
        else:
            QMessageBox.critical(self, "错误", "导出失败")

    def auto_detect_freezing(self):
        session = self._current_session()
        if not session:
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
            session.logical_path,
            session.crop_role,
            session.split_ratio,
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
        if not self._has_current_session():
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
            if self._has_current_session()
            else 0
        )
        total = self.time_formatter.format_time(self.video_model.duration if self._has_current_session() else 0)
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
        session = self._current_session()
        pixmap = self.thumbnail_cache.get(
            frame,
            crop_role=session.crop_role if session else None,
            split_ratio=session.split_ratio if session else None,
        )
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
        session = self._current_session()
        if not session or session.logical_path != source_video_path:
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
            session.logical_path,
            self.video_model.video_fps,
            self.video_model.total_frames,
            self._session_metadata(session),
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
            return self._save_dirty_sessions()
        if clicked == discard_button:
            return True
        if clicked == cancel_button:
            return False
        return False

    def _refresh_actions(self):
        session = self._current_session()
        has_video = session is not None
        current_dirty = (
            bool(session)
            and (session.annotation_model.dirty or session.metadata_dirty or not session.undo_stack.isClean())
        )
        self.save_action.setEnabled(has_video and current_dirty)
        self.export_action.setEnabled(has_video and self.annotation_model.count > 0)
        self.delete_action.setEnabled(has_video and self.annotation_model.count > 0)
        self.clear_action.setEnabled(has_video and self.annotation_model.count > 0)
        self.split_action.setEnabled(bool(self.video_model.video_path))
        if self._detection_thread is None:
            self.auto_detect_action.setEnabled(has_video)

    def _has_unsaved_changes(self) -> bool:
        return any(
            session.annotation_model.dirty
            or session.metadata_dirty
            or not session.undo_stack.isClean()
            for session in self.video_sessions
        )

    def _sync_dirty_from_undo_stack(self):
        for session in self.video_sessions:
            if not session.undo_stack.isClean():
                session.annotation_model.dirty = True
            elif not session.metadata_dirty:
                session.annotation_model.dirty = False
        self._refresh_actions()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and self._is_record_key_event(event):
            if not event.isAutoRepeat():
                self._toggle_pending_interval_at_current_frame()
            return True
        return super().eventFilter(watched, event)

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
        if self._is_record_key_event(event):
            if not event.isAutoRepeat():
                self._toggle_pending_interval_at_current_frame()
            return
        super().keyPressEvent(event)

    def _is_record_key_event(self, event) -> bool:
        if not self._has_current_session():
            return False
        if event.key() != Qt.Key.Key_Z or event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            return False
        if focus is not None and focus.window() is not self:
            return False
        active_window = QApplication.activeWindow()
        if active_window is not None and active_window is not self and active_window.window() is not self:
            return False
        return True

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
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self.thumbnail_cache.release()
            self.video_model.release()
            event.accept()
        else:
            event.ignore()


def run_qt_workbench():
    app = QApplication.instance() or QApplication([])
    window = QtAnnotationWorkbench()
    window.show()
    return app.exec()
