import unittest

from utils.timeline_viewport import TimelineViewport


class TimelineViewportTest(unittest.TestCase):
    def test_full_range_maps_frames_to_ratios(self):
        viewport = TimelineViewport()
        viewport.set_video(1000, 25.0)

        self.assertEqual(viewport.visible_start_frame, 0)
        self.assertEqual(viewport.visible_end_frame, 1000)
        self.assertEqual(viewport.ratio_to_frame(0.5), 500)
        self.assertAlmostEqual(viewport.frame_to_ratio(250), 0.25)
        self.assertEqual(viewport.ratio_to_frame(1.0, seekable=True), 999)

    def test_zoom_keeps_anchor_position(self):
        viewport = TimelineViewport()
        viewport.set_video(1000, 25.0)

        viewport.zoom_at_frame(500, 1.25)

        self.assertEqual(viewport.visible_span, 800)
        self.assertEqual(viewport.visible_start_frame, 100)
        self.assertEqual(viewport.visible_end_frame, 900)
        self.assertAlmostEqual(viewport.frame_to_ratio(500), 0.5)

    def test_zoom_respects_one_second_minimum_span(self):
        viewport = TimelineViewport()
        viewport.set_video(1000, 25.0)

        for _ in range(40):
            viewport.zoom_at_frame(500, 1.25)

        self.assertEqual(viewport.visible_span, 25)

    def test_pan_clamps_to_video_edges(self):
        viewport = TimelineViewport()
        viewport.set_video(1000, 25.0)
        viewport.zoom_at_frame(500, 2.0)

        self.assertEqual((viewport.visible_start_frame, viewport.visible_end_frame), (250, 750))

        viewport.pan_by_fraction(1)
        self.assertEqual((viewport.visible_start_frame, viewport.visible_end_frame), (500, 1000))

        viewport.pan_by_fraction(1)
        self.assertEqual((viewport.visible_start_frame, viewport.visible_end_frame), (500, 1000))

        viewport.pan_by_fraction(-1)
        self.assertEqual((viewport.visible_start_frame, viewport.visible_end_frame), (100, 600))


if __name__ == "__main__":
    unittest.main()
