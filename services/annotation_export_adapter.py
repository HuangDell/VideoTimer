"""Adapters between interval annotations and the legacy export service."""
from __future__ import annotations

from typing import Iterable, List

from models.annotation_model import AnnotationInterval
from models.record_model import TimeRecord


def intervals_to_time_records(
    intervals: Iterable[AnnotationInterval],
    fps: float,
) -> List[TimeRecord]:
    """Convert interval annotations to the paired TimeRecord format.

    The existing Excel exporter expects odd/even records to represent
    start/end points. Keeping this adapter small lets the new UI use a proper
    interval model without rewriting the export sheets in the first pass.
    """
    records: List[TimeRecord] = []
    previous_time = 0.0

    for interval in sorted(intervals, key=lambda item: (item.start_frame, item.end_frame)):
        start_time = _frame_to_seconds(interval.start_frame, fps)
        end_time = _frame_to_seconds(interval.end_frame, fps)
        for video_time, frame in (
            (start_time, interval.start_frame),
            (end_time, interval.end_frame),
        ):
            sequence = len(records) + 1
            interval_from_previous = 0.0 if sequence == 1 else video_time - previous_time
            records.append(
                TimeRecord(
                    sequence=sequence,
                    video_time=round(video_time, 3),
                    interval=round(interval_from_previous, 3),
                    frame=frame,
                )
            )
            previous_time = video_time

    return records


def _frame_to_seconds(frame: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return max(0, int(frame)) / fps
