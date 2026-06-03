import unittest

from models.export_types import ExportType
from services.export_service import EXPORT_INTERVALS, EXPORT_TYPES_WITH_FIRST_3MIN


class ExportTypeTest(unittest.TestCase):
    def test_export_type_values_are_stable(self):
        self.assertEqual(ExportType.LOOMING.value, "looming")
        self.assertEqual(ExportType.TRAINING.value, "training")
        self.assertEqual(ExportType.OFC.value, "ofc")
        self.assertEqual(ExportType.TEST.value, "test")

    def test_export_service_uses_shared_export_type_enum(self):
        self.assertEqual(
            set(EXPORT_INTERVALS),
            {ExportType.LOOMING, ExportType.TRAINING, ExportType.OFC, ExportType.TEST},
        )
        self.assertEqual(EXPORT_TYPES_WITH_FIRST_3MIN, {ExportType.LOOMING, ExportType.TRAINING})


if __name__ == "__main__":
    unittest.main()
