"""OpenCV-based freezing detection service."""
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from services.video_crop_service import apply_horizontal_crop


@dataclass(frozen=True)
class FreezingDetectionParams:
    """Tunable parameters for automatic freezing pre-labeling."""

    sample_rate: float = 10.0
    analysis_width: int = 320
    pixel_diff_threshold: int = 25
    motion_threshold: float = 0.0004
    min_freeze_duration: float = 0.5
    merge_gap: float = 0.3
    min_non_freeze_gap: float = 0.2
    smoothing_window: float = 0.3


@dataclass(frozen=True)
class FreezingInterval:
    """Detected freezing interval in video time."""

    start: float
    end: float
    duration: float
    start_frame: int
    end_frame: int


class FreezingDetectionService:
    """Detect likely freezing intervals from fixed-camera mouse videos."""

    def detect_freezing(
        self,
        video_path: str,
        fps: float,
        total_frames: int,
        params: Optional[FreezingDetectionParams] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        crop_role: Optional[str] = None,
        split_ratio: Optional[float] = None,
    ) -> List[FreezingInterval]:
        """Detect freezing intervals from a video file.

        Args:
            video_path: Path to the video file.
            fps: Video FPS from the loaded video model.
            total_frames: Total frame count from the loaded video model.
            params: Optional detection parameters.
            progress_callback: Optional callback receiving progress in [0, 1].

        Returns:
            Detected freezing intervals sorted by start time.
        """
        params = params or FreezingDetectionParams()
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        try:
            video_fps = fps if fps and fps > 0 else capture.get(cv2.CAP_PROP_FPS)
            if not video_fps or video_fps <= 0:
                raise ValueError("无法读取视频 FPS")

            frame_count = total_frames if total_frames and total_frames > 0 else int(
                capture.get(cv2.CAP_PROP_FRAME_COUNT)
            )
            sample_step = max(1, int(round(video_fps / max(params.sample_rate, 0.1))))
            sample_period = sample_step / video_fps

            times: List[float] = []
            motion_values: List[float] = []
            previous_frame: Optional[np.ndarray] = None
            frame_index = 0

            while True:
                ret, frame = capture.read()
                if not ret:
                    break

                frame = apply_horizontal_crop(frame, crop_role, split_ratio)
                processed_frame = self._preprocess_frame(frame, params)
                if previous_frame is None:
                    motion_ratio = 0.0
                else:
                    motion_ratio = self._calculate_motion_ratio(
                        previous_frame, processed_frame, params
                    )

                times.append(frame_index / video_fps)
                motion_values.append(motion_ratio)
                previous_frame = processed_frame

                if progress_callback and frame_count > 0:
                    progress_callback(min(frame_index / max(frame_count - 1, 1), 1.0))

                skipped = 0
                while skipped < sample_step - 1:
                    if not capture.grab():
                        frame_index += skipped + 1
                        break
                    skipped += 1

                if skipped < sample_step - 1:
                    break

                frame_index += sample_step

            if progress_callback:
                progress_callback(1.0)

            smoothed_motion = self._smooth_motion(
                motion_values, sample_step, video_fps, params
            )
            return self._motion_to_intervals(
                times, smoothed_motion, video_fps, frame_count, sample_period, params
            )
        finally:
            capture.release()

    def _preprocess_frame(
        self, frame: np.ndarray, params: FreezingDetectionParams
    ) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        if width > params.analysis_width:
            scale = params.analysis_width / width
            gray = cv2.resize(
                gray,
                (params.analysis_width, max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def _calculate_motion_ratio(
        self,
        previous_frame: np.ndarray,
        current_frame: np.ndarray,
        params: FreezingDetectionParams,
    ) -> float:
        frame_delta = cv2.absdiff(previous_frame, current_frame)
        _, thresholded = cv2.threshold(
            frame_delta, params.pixel_diff_threshold, 255, cv2.THRESH_BINARY
        )
        return float(cv2.countNonZero(thresholded)) / float(thresholded.size)

    def _smooth_motion(
        self,
        motion_values: Sequence[float],
        sample_step: int,
        fps: float,
        params: FreezingDetectionParams,
    ) -> List[float]:
        if not motion_values:
            return []

        effective_sample_rate = fps / sample_step
        window_size = max(1, int(round(params.smoothing_window * effective_sample_rate)))
        smoothed: List[float] = []

        for index in range(len(motion_values)):
            start_index = max(0, index - window_size + 1)
            window = motion_values[start_index : index + 1]
            smoothed.append(float(sum(window)) / len(window))

        return smoothed

    def _motion_to_intervals(
        self,
        times: Sequence[float],
        motion_values: Sequence[float],
        fps: float,
        total_frames: int,
        sample_period: float,
        params: FreezingDetectionParams,
    ) -> List[FreezingInterval]:
        raw_intervals = []
        current_start: Optional[float] = None

        for timestamp, motion in zip(times, motion_values):
            if motion < params.motion_threshold:
                if current_start is None:
                    current_start = timestamp
            elif current_start is not None:
                raw_intervals.append((current_start, timestamp))
                current_start = None

        if current_start is not None and times:
            raw_intervals.append((current_start, times[-1] + sample_period))

        merged = self._merge_intervals(raw_intervals, params)
        video_duration = total_frames / fps if total_frames and fps > 0 else None
        intervals: List[FreezingInterval] = []

        for start, end in merged:
            if video_duration is not None:
                end = min(end, video_duration)
            duration = end - start
            if duration + 1e-9 < params.min_freeze_duration:
                continue

            start_frame = max(0, int(round(start * fps)))
            end_frame = max(start_frame, int(round(end * fps)))
            if total_frames > 0:
                start_frame = min(start_frame, max(total_frames - 1, 0))
                end_frame = min(end_frame, total_frames)

            intervals.append(
                FreezingInterval(
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(duration, 3),
                    start_frame=start_frame,
                    end_frame=end_frame,
                )
            )

        return intervals

    def _merge_intervals(
        self,
        raw_intervals: Sequence[Tuple[float, float]],
        params: FreezingDetectionParams,
    ) -> List[Tuple[float, float]]:
        if not raw_intervals:
            return []

        merge_gap = max(params.merge_gap, params.min_non_freeze_gap)
        merged = [raw_intervals[0]]

        for start, end in raw_intervals[1:]:
            previous_start, previous_end = merged[-1]
            if start - previous_end <= merge_gap:
                merged[-1] = (previous_start, max(previous_end, end))
            else:
                merged.append((start, end))

        return merged
