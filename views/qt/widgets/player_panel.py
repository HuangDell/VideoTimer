"""Central player panel for video display, controls and timeline."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QStyle, QTabWidget, QVBoxLayout, QWidget

from views.qt.widgets.timeline import TimelineWidget
from views.qt.widgets.video_canvas import VideoCanvas


class PlayerPanel(QWidget):
    """Video canvas tabs plus playback controls and timeline."""

    play_requested = Signal()
    stop_requested = Signal()
    fullscreen_requested = Signal()
    speed_changed = Signal()
    seek_requested = Signal(int)
    interval_created = Signal(int, int)
    interval_changed = Signal(str, int, int)
    interval_selected = Signal(str)
    thumbnail_requested = Signal(int, QPoint)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.video_tabs = QTabWidget()
        self.video_canvas = VideoCanvas()
        self.video_tabs.addTab(self.video_canvas, "视频")
        layout.addWidget(self.video_tabs, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setText("播放")
        self.play_button.clicked.connect(self.play_requested.emit)
        controls.addWidget(self.play_button)

        self.stop_button = QPushButton("重置")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_requested.emit)
        controls.addWidget(self.stop_button)

        self.fullscreen_button = QPushButton("全屏")
        self.fullscreen_button.clicked.connect(self.fullscreen_requested.emit)
        controls.addWidget(self.fullscreen_button)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.8x", "1.0x", "1.5x", "2.0x", "3.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(lambda _text: self.speed_changed.emit())
        controls.addWidget(self.speed_combo)

        controls.addStretch(1)
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        self.video_info_label = QLabel("未加载视频")
        layout.addWidget(self.video_info_label)

        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.seek_requested.emit)
        self.timeline.interval_created.connect(self.interval_created.emit)
        self.timeline.interval_changed.connect(self.interval_changed.emit)
        self.timeline.interval_selected.connect(self.interval_selected.emit)
        self.timeline.thumbnail_requested.connect(self.thumbnail_requested.emit)
        layout.addWidget(self.timeline)
