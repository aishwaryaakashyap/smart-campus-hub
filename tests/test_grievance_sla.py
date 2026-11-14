import os
import unittest

from datetime import datetime, timedelta
from unittest.mock import patch

from services.grievance_sla import (
    get_sla_hours,
    calculate_sla_due_at,
)


class GrievanceSLATests(unittest.TestCase):

    @patch.dict(os.environ, {}, clear=True)
    def test_default_sla_hours_for_all_priorities(self):
        self.assertEqual(get_sla_hours("High"), 24)
        self.assertEqual(get_sla_hours("Medium"), 48)
        self.assertEqual(get_sla_hours("Low"), 72)

    def test_sla_deadline_calculation(self):
        start = datetime(2026, 11, 10, 10, 0, 0)

        expected = {
            "High": timedelta(hours=24),
            "Medium": timedelta(hours=48),
            "Low": timedelta(hours=72),
        }

        for priority, duration in expected.items():
            with self.subTest(priority=priority):
                self.assertEqual(
                    calculate_sla_due_at(priority, start),
                    start + duration
                )

    @patch.dict(os.environ, {"GRIEVANCE_SLA_HIGH_HOURS": "6"})
    def test_environment_variable_overrides_default(self):
        self.assertEqual(get_sla_hours("High"), 6)

    def test_rejects_invalid_priority(self):
        with self.assertRaises(ValueError):
            get_sla_hours("Urgent")

    def test_rejects_invalid_sla_configuration(self):
        invalid_values = ("abc", "0", "-2")

        for value in invalid_values:
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"GRIEVANCE_SLA_HIGH_HOURS": value}
                ):
                    with self.assertRaises(ValueError):
                        get_sla_hours("High")


if __name__ == "__main__":
    unittest.main()
