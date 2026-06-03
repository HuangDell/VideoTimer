import unittest

from views.qt.time_parsing import parse_time_text


class TimeParsingTest(unittest.TestCase):
    def test_parses_seconds(self):
        self.assertEqual(parse_time_text("12.345"), 12.345)

    def test_parses_hms(self):
        self.assertEqual(parse_time_text("01:02:03.500"), 3723.5)

    def test_rejects_invalid_text(self):
        with self.assertRaises(ValueError):
            parse_time_text("1:02")

    def test_rejects_negative_values(self):
        with self.assertRaises(ValueError):
            parse_time_text("-1:00:00")


if __name__ == "__main__":
    unittest.main()
