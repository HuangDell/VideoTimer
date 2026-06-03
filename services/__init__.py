"""服务层模块."""

__all__ = [
    "intervals_to_time_records",
    "ExportService",
]


def __getattr__(name):
    if name == "intervals_to_time_records":
        from .annotation_export_adapter import intervals_to_time_records

        return intervals_to_time_records
    if name == "ExportService":
        from .export_service import ExportService

        return ExportService
    raise AttributeError(name)
