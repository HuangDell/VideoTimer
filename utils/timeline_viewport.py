"""Frame viewport math shared by timeline widgets and tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimelineViewport:
    """Shared frame range used by the progress and interval tracks."""

    total_frames: int = 0
    fps: float = 30.0
    visible_start_frame: int = 0
    visible_end_frame: int = 0

    def set_video(self, total_frames: int, fps: float):
        self.total_frames = max(0, int(total_frames))
        self.fps = fps if fps > 0 else 30.0
        self.visible_start_frame = 0
        self.visible_end_frame = self.total_frames

    @property
    def visible_span(self) -> int:
        if self.total_frames <= 0:
            return 0
        return max(1, self.visible_end_frame - self.visible_start_frame)

    @property
    def minimum_span(self) -> int:
        if self.total_frames <= 0:
            return 0
        return min(self.total_frames, max(1, int(round(self.fps))))

    @property
    def is_zoomed(self) -> bool:
        return self.total_frames > 0 and self.visible_span < self.total_frames

    def can_pan_left(self) -> bool:
        return self.is_zoomed and self.visible_start_frame > 0

    def can_pan_right(self) -> bool:
        return self.is_zoomed and self.visible_end_frame < self.total_frames

    def set_visible_range(self, start_frame: int, end_frame: int):
        if self.total_frames <= 0:
            self.visible_start_frame = 0
            self.visible_end_frame = 0
            return

        span = max(1, int(round(end_frame - start_frame)))
        span = max(self.minimum_span, min(self.total_frames, span))
        max_start = max(0, self.total_frames - span)
        start = max(0, min(int(round(start_frame)), max_start))
        self.visible_start_frame = start
        self.visible_end_frame = start + span

    def zoom_at_frame(self, anchor_frame: int, scale: float):
        if self.total_frames <= 0 or scale <= 0:
            return
        old_span = self.visible_span
        if old_span <= 0:
            return
        anchor = self.clamp_frame(anchor_frame)
        anchor_ratio = (anchor - self.visible_start_frame) / old_span
        anchor_ratio = max(0.0, min(anchor_ratio, 1.0))
        new_span = max(1, int(round(old_span / scale)))
        new_start = int(round(anchor - anchor_ratio * new_span))
        self.set_visible_range(new_start, new_start + new_span)

    def pan_by_fraction(self, direction: int, fraction: float = 0.8):
        if not self.is_zoomed:
            return
        step = max(1, int(round(self.visible_span * fraction)))
        delta = step if direction > 0 else -step
        self.set_visible_range(
            self.visible_start_frame + delta,
            self.visible_end_frame + delta,
        )

    def clamp_frame(self, frame: int, seekable: bool = False) -> int:
        if self.total_frames <= 0:
            return 0
        max_frame = self.total_frames - 1 if seekable else self.total_frames
        return max(0, min(int(frame), max_frame))

    def clamp_visible_frame(self, frame: int, seekable: bool = False) -> int:
        if self.total_frames <= 0:
            return 0
        lower = self.visible_start_frame
        upper = self.visible_end_frame
        if seekable:
            upper = min(upper - 1, self.total_frames - 1)
        return max(lower, min(int(frame), max(lower, upper)))

    def frame_to_ratio(self, frame: int) -> float:
        if self.visible_span <= 0:
            return 0.0
        frame = self.clamp_visible_frame(frame)
        return (frame - self.visible_start_frame) / self.visible_span

    def ratio_to_frame(self, ratio: float, seekable: bool = False) -> int:
        if self.visible_span <= 0:
            return 0
        ratio = max(0.0, min(float(ratio), 1.0))
        frame = round(self.visible_start_frame + ratio * self.visible_span)
        return self.clamp_visible_frame(frame, seekable=seekable)
