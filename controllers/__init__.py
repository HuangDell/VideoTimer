"""控制器模块."""

__all__ = ["VideoController", "RecordController", "MainController"]


def __getattr__(name):
    if name == "VideoController":
        from .video_controller import VideoController

        return VideoController
    if name == "RecordController":
        from .record_controller import RecordController

        return RecordController
    if name == "MainController":
        from .main_controller import MainController

        return MainController
    raise AttributeError(name)
