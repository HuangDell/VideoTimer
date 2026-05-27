"""视图模块."""

__all__ = [
    "MainWindow",
    "VideoPanel",
    "TimingPanel",
    "InstanceSelector",
    "ExportDialog",
    "ExportType",
    "QtAnnotationWorkbench",
]


def __getattr__(name):
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    if name == "VideoPanel":
        from .video_panel import VideoPanel

        return VideoPanel
    if name == "TimingPanel":
        from .timing_panel import TimingPanel

        return TimingPanel
    if name == "InstanceSelector":
        from .instance_selector import InstanceSelector

        return InstanceSelector
    if name in {"ExportDialog", "ExportType"}:
        from .export_dialog import ExportDialog, ExportType

        return {"ExportDialog": ExportDialog, "ExportType": ExportType}[name]
    if name == "QtAnnotationWorkbench":
        from .qt_workbench import QtAnnotationWorkbench

        return QtAnnotationWorkbench
    raise AttributeError(name)
