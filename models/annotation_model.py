"""Editable interval annotation model for the PySide6 workbench."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


SIDECAR_SCHEMA_VERSION = 1
DEFAULT_LABEL = "freezing"


@dataclass(frozen=True)
class AnnotationInterval:
    """A single freezing interval stored in frame coordinates.

    ``start_frame`` is inclusive and ``end_frame`` is exclusive. This makes
    duration calculations stable and allows an interval to end at total_frames.
    """

    id: str
    start_frame: int
    end_frame: int
    label: str = DEFAULT_LABEL

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AnnotationInterval":
        return cls(
            id=str(payload.get("id") or uuid4()),
            label=str(payload.get("label") or DEFAULT_LABEL),
            start_frame=int(payload["start_frame"]),
            end_frame=int(payload["end_frame"]),
        )


@dataclass
class AnnotationDocument:
    """Serializable annotation document for a single video."""

    schema_version: int = SIDECAR_SCHEMA_VERSION
    video_metadata: Dict[str, Any] = field(default_factory=dict)
    intervals: List[AnnotationInterval] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "video_metadata": self.video_metadata,
            "intervals": [interval.to_dict() for interval in self.intervals],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AnnotationDocument":
        intervals = [
            AnnotationInterval.from_dict(item)
            for item in payload.get("intervals", [])
        ]
        return cls(
            schema_version=int(payload.get("schema_version", SIDECAR_SCHEMA_VERSION)),
            video_metadata=dict(payload.get("video_metadata", {})),
            intervals=intervals,
            updated_at=str(payload.get("updated_at", "")),
        )


class AnnotationModel:
    """Manage non-overlapping interval annotations for one video."""

    def __init__(self):
        self.video_path: str = ""
        self.video_fps: float = 30.0
        self.total_frames: int = 0
        self.video_metadata: Dict[str, Any] = {}
        self._intervals: List[AnnotationInterval] = []
        self.dirty: bool = False

    @property
    def intervals(self) -> List[AnnotationInterval]:
        return list(self._intervals)

    @property
    def count(self) -> int:
        return len(self._intervals)

    def set_video_context(self, video_path: str, fps: float, total_frames: int):
        self.video_path = video_path
        self.video_fps = fps if fps > 0 else 30.0
        self.total_frames = max(0, int(total_frames))
        self.video_metadata = {
            "path": video_path,
            "filename": Path(video_path).name,
            "fps": self.video_fps,
            "total_frames": self.total_frames,
            "duration": self.frame_to_seconds(self.total_frames),
        }
        self._intervals = []
        self.dirty = False

    def frame_to_seconds(self, frame: int) -> float:
        if self.video_fps <= 0:
            return 0.0
        return max(0, int(frame)) / self.video_fps

    def seconds_to_frame(self, seconds: float) -> int:
        return self.clamp_frame(round(max(0.0, seconds) * self.video_fps))

    def clamp_frame(self, frame: int) -> int:
        return max(0, min(int(frame), self.total_frames))

    def add_interval(
        self,
        start_frame: int,
        end_frame: int,
        label: str = DEFAULT_LABEL,
        interval_id: Optional[str] = None,
    ) -> AnnotationInterval:
        interval = AnnotationInterval(
            id=interval_id or str(uuid4()),
            label=label or DEFAULT_LABEL,
            start_frame=self.clamp_frame(start_frame),
            end_frame=self.clamp_frame(end_frame),
        )
        self._validate_interval(interval)
        self._intervals.append(interval)
        self._intervals.sort(key=lambda item: (item.start_frame, item.end_frame))
        self.dirty = True
        return interval

    def validate_interval_data(
        self,
        start_frame: int,
        end_frame: int,
        label: str = DEFAULT_LABEL,
        interval_id: Optional[str] = None,
        ignore_id: Optional[str] = None,
    ):
        """Validate a potential interval without mutating the model."""
        interval = AnnotationInterval(
            id=interval_id or str(uuid4()),
            label=label or DEFAULT_LABEL,
            start_frame=self.clamp_frame(start_frame),
            end_frame=self.clamp_frame(end_frame),
        )
        self._validate_interval(interval, ignore_id=ignore_id)

    def update_interval(
        self,
        interval_id: str,
        start_frame: int,
        end_frame: int,
        label: Optional[str] = None,
    ) -> AnnotationInterval:
        existing = self.get_interval(interval_id)
        if existing is None:
            raise KeyError(f"Annotation interval not found: {interval_id}")

        updated = AnnotationInterval(
            id=existing.id,
            label=label or existing.label,
            start_frame=self.clamp_frame(start_frame),
            end_frame=self.clamp_frame(end_frame),
        )
        self._validate_interval(updated, ignore_id=interval_id)
        self._intervals = [
            updated if item.id == interval_id else item
            for item in self._intervals
        ]
        self._intervals.sort(key=lambda item: (item.start_frame, item.end_frame))
        self.dirty = True
        return updated

    def delete_interval(self, interval_id: str) -> AnnotationInterval:
        existing = self.get_interval(interval_id)
        if existing is None:
            raise KeyError(f"Annotation interval not found: {interval_id}")
        self._intervals = [item for item in self._intervals if item.id != interval_id]
        self.dirty = True
        return existing

    def replace_intervals(self, intervals: Iterable[AnnotationInterval]):
        normalized: List[AnnotationInterval] = []
        for interval in sorted(intervals, key=lambda item: (item.start_frame, item.end_frame)):
            item = AnnotationInterval(
                id=interval.id or str(uuid4()),
                label=interval.label or DEFAULT_LABEL,
                start_frame=self.clamp_frame(interval.start_frame),
                end_frame=self.clamp_frame(interval.end_frame),
            )
            self._validate_interval_against_list(item, normalized)
            normalized.append(item)

        self._intervals = normalized
        self.dirty = True

    def get_interval(self, interval_id: str) -> Optional[AnnotationInterval]:
        for interval in self._intervals:
            if interval.id == interval_id:
                return interval
        return None

    def neighbor_bounds(self, interval_id: str) -> tuple[int, int]:
        """Return the allowed [left, right] frame boundary for editing an interval."""
        ordered = self.intervals
        for index, interval in enumerate(ordered):
            if interval.id != interval_id:
                continue
            left = ordered[index - 1].end_frame if index > 0 else 0
            right = ordered[index + 1].start_frame if index + 1 < len(ordered) else self.total_frames
            return left, right
        return 0, self.total_frames

    @staticmethod
    def sidecar_path_for(video_path: str) -> Path:
        path = Path(video_path)
        return path.with_name(f"{path.stem}.videotimer.json")

    def load_sidecar(self, video_path: Optional[str] = None) -> bool:
        target = self.sidecar_path_for(video_path or self.video_path)
        if not target.exists():
            self._intervals = []
            self.dirty = False
            return False

        with target.open("r", encoding="utf-8") as file:
            document = AnnotationDocument.from_dict(json.load(file))

        self._intervals = []
        for interval in sorted(document.intervals, key=lambda item: (item.start_frame, item.end_frame)):
            normalized = AnnotationInterval(
                id=interval.id,
                label=interval.label,
                start_frame=self.clamp_frame(interval.start_frame),
                end_frame=self.clamp_frame(interval.end_frame),
            )
            self._validate_interval_against_list(normalized, self._intervals)
            self._intervals.append(normalized)

        self.dirty = False
        return True

    def save_sidecar(self, video_path: Optional[str] = None) -> Path:
        target = self.sidecar_path_for(video_path or self.video_path)
        document = AnnotationDocument(
            video_metadata=self.video_metadata,
            intervals=self.intervals,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with target.open("w", encoding="utf-8") as file:
            json.dump(document.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")
        self.dirty = False
        return target

    def _validate_interval(
        self,
        interval: AnnotationInterval,
        ignore_id: Optional[str] = None,
    ):
        candidates = [item for item in self._intervals if item.id != ignore_id]
        self._validate_interval_against_list(interval, candidates)

    @staticmethod
    def _validate_interval_against_list(
        interval: AnnotationInterval,
        candidates: Iterable[AnnotationInterval],
    ):
        if interval.end_frame <= interval.start_frame:
            raise ValueError("区间结束时间必须晚于开始时间")
        if interval.label != DEFAULT_LABEL:
            raise ValueError("首版仅支持 freezing 标注")

        for existing in candidates:
            overlaps = (
                interval.start_frame < existing.end_frame
                and interval.end_frame > existing.start_frame
            )
            if overlaps:
                raise ValueError("标注区间不能重叠")
