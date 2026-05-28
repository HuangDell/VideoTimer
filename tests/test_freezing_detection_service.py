import os
import tempfile
from unittest.mock import patch
import unittest

try:
    import cv2
    import numpy as np

    from services.freezing_detection_service import (
        FreezingDetectionParams,
        FreezingDetectionService,
    )
    from services.video_crop_service import CROP_LOWER, CROP_UPPER
except ModuleNotFoundError as exc:
    cv2 = None
    np = None
    OPENCV_IMPORT_ERROR = exc
else:
    OPENCV_IMPORT_ERROR = None


class FakeCapture:
    def __init__(self, frames, fps):
        self.frames = frames
        self.fps = fps
        self.index = 0

    def isOpened(self):
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return len(self.frames)
        return 0

    def read(self):
        if self.index >= len(self.frames):
            return False, None
        frame = self.frames[self.index]
        self.index += 1
        return True, frame.copy()

    def grab(self):
        if self.index >= len(self.frames):
            return False
        self.index += 1
        return True

    def release(self):
        pass


@unittest.skipIf(OPENCV_IMPORT_ERROR is not None, f"OpenCV unavailable: {OPENCV_IMPORT_ERROR}")
class FreezingDetectionServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = FreezingDetectionService()

    def test_motion_to_intervals_filters_short_segments_and_merges_short_gaps(self):
        params = FreezingDetectionParams(
            motion_threshold=0.003,
            min_freeze_duration=0.5,
            merge_gap=0.3,
            min_non_freeze_gap=0.2,
        )
        times = [index / 10 for index in range(25)]
        motion_values = [0.01 for _ in times]

        for index in range(0, 5):
            motion_values[index] = 0.0
        for index in range(7, 12):
            motion_values[index] = 0.0
        for index in range(20, 24):
            motion_values[index] = 0.0

        intervals = self.service._motion_to_intervals(
            times, motion_values, 10.0, 250, 0.1, params
        )

        self.assertEqual(len(intervals), 1)
        self.assertAlmostEqual(intervals[0].start, 0.0)
        self.assertAlmostEqual(intervals[0].end, 1.2)
        self.assertAlmostEqual(intervals[0].duration, 1.2)
        self.assertEqual(intervals[0].start_frame, 0)
        self.assertEqual(intervals[0].end_frame, 12)

    def test_motion_to_intervals_keeps_exact_minimum_duration(self):
        params = FreezingDetectionParams(
            motion_threshold=0.003,
            min_freeze_duration=0.5,
            merge_gap=0.1,
            min_non_freeze_gap=0.1,
        )
        times = [index / 10 for index in range(20)]
        motion_values = [0.01 for _ in times]
        for index in range(10, 15):
            motion_values[index] = 0.0

        intervals = self.service._motion_to_intervals(
            times, motion_values, 10.0, 200, 0.1, params
        )

        self.assertEqual(len(intervals), 1)
        self.assertAlmostEqual(intervals[0].start, 1.0)
        self.assertAlmostEqual(intervals[0].end, 1.5)
        self.assertAlmostEqual(intervals[0].duration, 0.5)

    def test_detect_freezing_from_synthetic_video(self):
        fps = 10.0
        frame_size = (64, 64)
        params = FreezingDetectionParams(
            sample_rate=10.0,
            analysis_width=64,
            pixel_diff_threshold=5,
            motion_threshold=0.01,
            min_freeze_duration=0.5,
            merge_gap=0.1,
            min_non_freeze_gap=0.1,
            smoothing_window=0.1,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, "synthetic_freezing.avi")
            writer = cv2.VideoWriter(
                video_path,
                cv2.VideoWriter_fourcc(*"MJPG"),
                fps,
                frame_size,
            )
            if not writer.isOpened():
                self.skipTest("OpenCV MJPG writer is not available")

            try:
                for _ in range(8):
                    writer.write(self._mouse_frame(frame_size, 20))
                for index in range(8):
                    writer.write(self._mouse_frame(frame_size, 4 + index * 4))
                for _ in range(8):
                    writer.write(self._mouse_frame(frame_size, 32))
            finally:
                writer.release()

            intervals = self.service.detect_freezing(
                video_path,
                fps,
                24,
                params,
            )

        self.assertGreaterEqual(len(intervals), 2)
        self.assertAlmostEqual(intervals[0].start, 0.0)
        self.assertGreaterEqual(intervals[0].duration, 0.5)
        self.assertGreaterEqual(intervals[-1].start, 1.5)
        self.assertGreaterEqual(intervals[-1].duration, 0.5)

    def test_detect_freezing_applies_virtual_crop(self):
        fps = 1.0
        frames = []
        for index in range(4):
            frame = np.zeros((4, 4, 3), dtype=np.uint8)
            frame[:2, :] = 255 if index % 2 else 0
            frames.append(frame)
        params = FreezingDetectionParams(
            sample_rate=1.0,
            analysis_width=4,
            pixel_diff_threshold=5,
            motion_threshold=0.1,
            min_freeze_duration=1.1,
            merge_gap=0.1,
            min_non_freeze_gap=0.1,
            smoothing_window=0.1,
        )

        with patch(
            "services.freezing_detection_service.cv2.VideoCapture",
            lambda _path: FakeCapture(frames, fps),
        ):
            lower_intervals = self.service.detect_freezing(
                "synthetic.avi",
                fps,
                len(frames),
                params,
                crop_role=CROP_LOWER,
                split_ratio=0.5,
            )

        with patch(
            "services.freezing_detection_service.cv2.VideoCapture",
            lambda _path: FakeCapture(frames, fps),
        ):
            upper_intervals = self.service.detect_freezing(
                "synthetic.avi",
                fps,
                len(frames),
                params,
                crop_role=CROP_UPPER,
                split_ratio=0.5,
            )

        self.assertEqual(len(lower_intervals), 1)
        self.assertEqual(lower_intervals[0].start_frame, 0)
        self.assertEqual(lower_intervals[0].end_frame, 4)
        self.assertEqual(upper_intervals, [])

    def _mouse_frame(self, frame_size, square_x):
        frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
        frame[24:40, square_x:square_x + 16] = 255
        return frame


if __name__ == "__main__":
    unittest.main()
