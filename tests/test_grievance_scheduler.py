import unittest
from contextlib import nullcontext
from unittest.mock import patch

import scripts.run_grievance_scheduler as scheduler


class GrievanceSchedulerTests(unittest.TestCase):

    def setUp(self):
        scheduler.running = True

    def tearDown(self):
        scheduler.running = False

    def test_runs_immediately_and_stops_cleanly(self):
        sleep_calls = []

        def stop_after_sleep(seconds):
            sleep_calls.append(seconds)
            scheduler.stop_scheduler(None, None)

        with (
            patch.object(
                scheduler.app,
                "app_context",
                return_value=nullcontext(),
            ),
            patch.object(scheduler, "escalate_overdue_grievances", return_value=2) as escalate,
            patch.object(scheduler.signal, "signal"),
            patch.object(scheduler.time, "sleep", side_effect=stop_after_sleep),
        ):
            scheduler.run_scheduler()

        escalate.assert_called_once_with()
        self.assertEqual(sleep_calls, [1])
        self.assertFalse(scheduler.running)

    def test_continues_after_an_unexpected_cycle_error(self):
        sleep_calls = []

        def stop_during_second_wait(seconds):
            sleep_calls.append(seconds)

            if len(sleep_calls) == 4:
                scheduler.stop_scheduler(None, None)

        with (
            patch.object(
                scheduler.app,
                "app_context",
                return_value=nullcontext(),
            ),
            patch.object(
                scheduler,
                "escalate_overdue_grievances",
                side_effect=[RuntimeError("Simulated cycle failure"), 1],
            ) as escalate,
            patch.object(scheduler.signal, "signal"),
            patch.object(scheduler, "INTERVAL_SECONDS", 2),
            patch.object(
                scheduler.time,
                "sleep",
                side_effect=stop_during_second_wait,
            ),
        ):
            scheduler.run_scheduler()

        self.assertEqual(escalate.call_count, 2)
        self.assertEqual(sleep_calls, [1, 1, 1, 1])
        self.assertFalse(scheduler.running)

    def test_resets_running_state_when_started_again(self):
        scheduler.running = False

        sleep_calls = []

        def stop_after_sleep(seconds):
            sleep_calls.append(seconds)
            scheduler.stop_scheduler(None, None)

        with (
            patch.object(
                scheduler.app,
                "app_context",
                return_value=nullcontext(),
            ),
            patch.object(scheduler, "escalate_overdue_grievances", return_value=0) as escalate,
            patch.object(scheduler.signal, "signal"),
            patch.object(scheduler.time, "sleep", side_effect=stop_after_sleep),
        ):
            scheduler.run_scheduler()

        escalate.assert_called_once_with()
        self.assertEqual(sleep_calls, [1])
        self.assertFalse(scheduler.running)


if __name__ == "__main__":
    unittest.main()
