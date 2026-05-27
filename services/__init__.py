"""服务层模块."""

__all__ = [
    "intervals_to_time_records",
    "VideoService",
    "ExportService",
    "KeyboardService",
]


def __getattr__(name):
    if name == "intervals_to_time_records":
        from .annotation_export_adapter import intervals_to_time_records

        return intervals_to_time_records
    if name == "VideoService":
        from .video_service import VideoService

        return VideoService
    if name == "ExportService":
        from .export_service import ExportService

        return ExportService
    if name == "KeyboardService":
        from .keyboard_service import KeyboardService

        return KeyboardService
    raise AttributeError(name)
