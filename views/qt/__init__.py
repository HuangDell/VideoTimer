"""PySide6 UI package."""
from __future__ import annotations

__all__ = ["QtAnnotationWorkbench", "run_qt_workbench"]


def __getattr__(name: str):
    if name in __all__:
        from views.qt.workbench import QtAnnotationWorkbench, run_qt_workbench

        return {
            "QtAnnotationWorkbench": QtAnnotationWorkbench,
            "run_qt_workbench": run_qt_workbench,
        }[name]
    raise AttributeError(name)
