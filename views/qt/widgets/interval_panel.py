"""Interval table panel."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class IntervalPanel(QWidget):
    """Controls and editable table for annotation intervals."""

    delete_requested = Signal()
    clear_requested = Signal()
    item_clicked = Signal(object)
    item_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        button_row = QHBoxLayout()
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_requested.emit)
        button_row.addWidget(self.delete_button)

        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_requested.emit)
        button_row.addWidget(self.clear_button)
        layout.addLayout(button_row)

        self.interval_table = QTableWidget(0, 3)
        self.interval_table.setHorizontalHeaderLabels(["start_time", "end_time", "duration"])
        self.interval_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.interval_table.verticalHeader().setVisible(False)
        self.interval_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.interval_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.interval_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.interval_table.itemClicked.connect(self.item_clicked.emit)
        self.interval_table.itemChanged.connect(self.item_changed.emit)
        layout.addWidget(self.interval_table, 1)

        self.stats_label = QLabel("区间数: 0")
        layout.addWidget(self.stats_label)
