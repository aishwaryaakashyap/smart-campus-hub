import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from services.grievance_sla import (
    GRIEVANCE_SLA_WORKING_DAYS,
    get_sla_working_days,
    get_public_holidays,
    calculate_sla_due_at,
)


class GrievanceSLATests(unittest.TestCase):

    def test_all_priorities_have_fixed_four_working_day_sla(self):
        self.assertEqual(GRIEVANCE_SLA_WORKING_DAYS, 4)

        for priority in ("High", "Medium", "Low"):
            with self.subTest(priority=priority):
                self.assertEqual(get_sla_working_days(priority), 4)

    def test_deadline_skips_weekend(self):
        start = datetime(2026, 11, 20, 10, 0, 0)  # Friday
        expected = datetime(2026, 11, 26, 10, 0, 0)  # Thursday

        for priority in ("High", "Medium", "Low"):
            with self.subTest(priority=priority):
                self.assertEqual(
                    calculate_sla_due_at(priority, start),
                    expected
                )

    def test_deadline_skips_configured_public_holiday(self):
        start = datetime(2026, 11, 20, 10, 0, 0)  # Friday
        holidays = {date(2026, 11, 23)}  # Monday
        expected = datetime(2026, 11, 27, 10, 0, 0)  # Friday

        self.assertEqual(
            calculate_sla_due_at("Medium", start, holidays),
            expected
        )

    def test_deadline_preserves_start_time(self):
        start = datetime(2026, 11, 16, 14, 35, 20)
        expected = datetime(2026, 11, 20, 14, 35, 20)

        self.assertEqual(
            calculate_sla_due_at("Low", start),
            expected
        )

    def test_environment_public_holidays_are_loaded(self):
        with patch.dict(
            os.environ,
            {"GRIEVANCE_PUBLIC_HOLIDAYS": "2026-11-23, 2026-12-25"}
        ):
            self.assertEqual(
                get_public_holidays(),
                {date(2026, 11, 23), date(2026, 12, 25)}
            )

    def test_invalid_public_holiday_configuration_is_rejected(self):
        with patch.dict(
            os.environ,
            {"GRIEVANCE_PUBLIC_HOLIDAYS": "not-a-date"}
        ):
            with self.assertRaises(ValueError):
                get_public_holidays()

    def test_rejects_invalid_priority(self):
        with self.assertRaises(ValueError):
            get_sla_working_days("Urgent")

        with self.assertRaises(ValueError):
            calculate_sla_due_at("Urgent")


if __name__ == "__main__":
    unittest.main()
