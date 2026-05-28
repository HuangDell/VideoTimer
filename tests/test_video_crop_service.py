import unittest
from pathlib import Path

import numpy as np

from services.video_crop_service import (
    CROP_LOWER,
    CROP_UPPER,
    apply_horizontal_crop,
    horizontal_crop_bounds,
    logical_split_video_path,
)


class VideoCropServiceTest(unittest.TestCase):
    def test_horizontal_crop_uses_split_ratio(self):
        frame = np.arange(6 * 4 * 3, dtype=np.uint8).reshape((6, 4, 3))

        upper = apply_horizontal_crop(frame, CROP_UPPER, 0.5)
        lower = apply_horizontal_crop(frame, CROP_LOWER, 0.5)

        self.assertEqual(upper.shape, (3, 4, 3))
        self.assertEqual(lower.shape, (3, 4, 3))
        np.testing.assert_array_equal(upper, frame[:3, :])
        np.testing.assert_array_equal(lower, frame[3:, :])

    def test_horizontal_crop_keeps_both_sides_visible_at_edges(self):
        self.assertEqual(horizontal_crop_bounds(10, 0.0, CROP_UPPER), (0, 1))
        self.assertEqual(horizontal_crop_bounds(10, 1.0, CROP_LOWER), (9, 10))

    def test_logical_split_video_path_suffixes_stem(self):
        source_path = "videos/mouse.avi"
        self.assertEqual(
            logical_split_video_path(source_path, 2),
            str(Path("videos") / "mouse_2.avi"),
        )


if __name__ == "__main__":
    unittest.main()
