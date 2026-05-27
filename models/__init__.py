"""数据模型模块."""

__all__ = [
    "AnnotationDocument",
    "AnnotationInterval",
    "AnnotationModel",
    "VideoModel",
    "RecordModel",
]


def __getattr__(name):
    if name in {"AnnotationDocument", "AnnotationInterval", "AnnotationModel"}:
        from .annotation_model import AnnotationDocument, AnnotationInterval, AnnotationModel

        return {
            "AnnotationDocument": AnnotationDocument,
            "AnnotationInterval": AnnotationInterval,
            "AnnotationModel": AnnotationModel,
        }[name]
    if name == "VideoModel":
        from .video_model import VideoModel

        return VideoModel
    if name == "RecordModel":
        from .record_model import RecordModel

        return RecordModel
    raise AttributeError(name)
