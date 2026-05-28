import json
from pathlib import Path
import tempfile
import unittest

from models.annotation_model import AnnotationInterval, AnnotationModel
from services.annotation_export_adapter import intervals_to_time_records


class AnnotationModelTest(unittest.TestCase):
    def setUp(self):
        self.model = AnnotationModel()
        self.model.set_video_context("mouse.avi", 10.0, 100)

    def test_adds_intervals_sorted_and_rejects_overlap(self):
        second = self.model.add_interval(40, 50)
        first = self.model.add_interval(10, 20)

        self.assertEqual([item.id for item in self.model.intervals], [first.id, second.id])
        with self.assertRaises(ValueError):
            self.model.add_interval(15, 30)

    def test_update_clamps_to_video_bounds_and_keeps_non_overlap(self):
        interval = self.model.add_interval(10, 20)
        self.model.update_interval(interval.id, -50, 25)

        updated = self.model.get_interval(interval.id)
        self.assertEqual(updated.start_frame, 0)
        self.assertEqual(updated.end_frame, 25)

        self.model.add_interval(30, 40)
        with self.assertRaises(ValueError):
            self.model.update_interval(interval.id, 0, 31)

    def test_delete_and_replace_intervals(self):
        interval = self.model.add_interval(10, 20)
        deleted = self.model.delete_interval(interval.id)

        self.assertEqual(deleted.id, interval.id)
        self.assertEqual(self.model.count, 0)

        self.model.replace_intervals(
            [
                AnnotationInterval("b", 30, 35),
                AnnotationInterval("a", 5, 10),
            ]
        )
        self.assertEqual([item.id for item in self.model.intervals], ["a", "b"])

    def test_sidecar_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "mouse.avi"
            video_path.touch()
            self.model.set_video_context(str(video_path), 10.0, 100)
            self.model.add_interval(10, 20)
            sidecar_path = self.model.save_sidecar()

            self.assertEqual(sidecar_path.name, "mouse.videotimer.json")
            self.assertFalse(self.model.dirty)

            loaded = AnnotationModel()
            loaded.set_video_context(str(video_path), 10.0, 100)
            self.assertTrue(loaded.load_sidecar())
            self.assertEqual(len(loaded.intervals), 1)
            self.assertEqual(loaded.intervals[0].start_frame, 10)
            self.assertEqual(loaded.intervals[0].end_frame, 20)

    def test_virtual_split_sidecar_uses_logical_name_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "mouse.avi"
            logical_path = Path(directory) / "mouse_1.avi"
            self.model.set_video_context(
                str(logical_path),
                10.0,
                100,
                {
                    "source_video_path": str(source_path),
                    "crop_role": "upper",
                    "split_ratio": 0.42,
                },
            )
            sidecar_path = self.model.save_sidecar()
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))

            self.assertEqual(sidecar_path.name, "mouse_1.videotimer.json")
            self.assertEqual(payload["video_metadata"]["path"], str(logical_path))
            self.assertEqual(payload["video_metadata"]["source_video_path"], str(source_path))
            self.assertEqual(payload["video_metadata"]["crop_role"], "upper")
            self.assertEqual(payload["video_metadata"]["split_ratio"], 0.42)

    def test_sidecar_load_clamps_older_metadata_to_current_video(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "mouse.avi"
            sidecar_path = Path(directory) / "mouse.videotimer.json"
            sidecar_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "video_metadata": {"total_frames": 500},
                        "intervals": [
                            {
                                "id": "from-longer-video",
                                "label": "freezing",
                                "start_frame": 80,
                                "end_frame": 150,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            loaded = AnnotationModel()
            loaded.set_video_context(str(video_path), 10.0, 100)
            loaded.load_sidecar()

            self.assertEqual(loaded.intervals[0].start_frame, 80)
            self.assertEqual(loaded.intervals[0].end_frame, 100)

    def test_intervals_to_time_records_adapter(self):
        intervals = [
            AnnotationInterval("first", 10, 25),
            AnnotationInterval("second", 40, 55),
        ]

        records = intervals_to_time_records(intervals, 10.0)

        self.assertEqual([record.sequence for record in records], [1, 2, 3, 4])
        self.assertEqual([record.video_time for record in records], [1.0, 2.5, 4.0, 5.5])
        self.assertEqual([record.frame for record in records], [10, 25, 40, 55])


if __name__ == "__main__":
    unittest.main()
