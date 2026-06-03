"""Undo commands for annotation mutations."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtGui import QUndoCommand

from models.annotation_model import AnnotationInterval

if TYPE_CHECKING:
    from views.qt.workbench import QtAnnotationWorkbench


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
