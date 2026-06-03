"""File browser panel for selecting videos."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtWidgets import QFileSystemModel, QPushButton, QTreeView, QVBoxLayout, QWidget


class FilePanel(QWidget):
    """Video file browser with an explicit folder picker action."""

    folder_requested = Signal()
    video_selected = Signal(str)

    def __init__(self, video_extensions: Iterable[str], root_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.video_extensions = {suffix.lower() for suffix in video_extensions}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.open_folder_button = QPushButton("打开文件夹")
        self.open_folder_button.clicked.connect(self.folder_requested.emit)
        layout.addWidget(self.open_folder_button)

        self.file_model = QFileSystemModel(self)
        self.file_model.setRootPath(str(root_path))
        filters = [f"*{suffix}" for suffix in sorted(self.video_extensions)]
        filters.extend(f"*{suffix.upper()}" for suffix in sorted(self.video_extensions))
        self.file_model.setNameFilters(filters)
        self.file_model.setNameFilterDisables(False)

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(root_path)))
        self.file_tree.setHeaderHidden(True)
        for column in (1, 2, 3):
            self.file_tree.hideColumn(column)
        self.file_tree.doubleClicked.connect(self._on_file_double_clicked)
        layout.addWidget(self.file_tree, 1)

    def set_root_folder(self, folder: str):
        self.file_model.setRootPath(folder)
        self.file_tree.setRootIndex(self.file_model.index(folder))

    def _on_file_double_clicked(self, index: QModelIndex):
        path = Path(self.file_model.filePath(index))
        if path.is_file() and path.suffix.lower() in self.video_extensions:
            self.video_selected.emit(str(path))
