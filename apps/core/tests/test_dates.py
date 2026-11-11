import unittest
from datetime import date, datetime, timezone

from apps.core.dates import add_months


class AddMonthsTests(unittest.TestCase):
    def test_six_calendar_months(self):
        self.assertEqual(add_months(date(2026, 1, 15), 6), date(2026, 7, 15))

    def test_end_of_month_clamped(self):
        self.assertEqual(add_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        self.assertEqual(add_months(date(2027, 8, 31), 6), date(2028, 2, 29))  # ano bissexto

    def test_year_rollover(self):
        self.assertEqual(add_months(date(2026, 11, 6), 6), date(2027, 5, 6))

    def test_not_a_180_day_approximation(self):
        start = date(2026, 1, 1)
        self.assertNotEqual((add_months(start, 6) - start).days, 180)

    def test_preserves_time_and_tz(self):
        value = datetime(2026, 3, 31, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(add_months(value, 6), datetime(2026, 9, 30, 14, 30, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
