"""Standalone scheduler for automatic grievance SLA escalation."""

import logging
import signal
import sys
import time
from pathlib import Path

# Add the project root so direct script execution can import app.py.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app
from services.grievance_escalation import escalate_overdue_grievances


INTERVAL_SECONDS = 300

logger = logging.getLogger("grievance_scheduler")

running = True


def stop_scheduler(signum, frame):
    """Request a clean shutdown after the current cycle."""
    global running
    running = False
    logger.info("Shutdown signal received. Stopping scheduler...")


def run_scheduler():
    """Run grievance escalation immediately and then every five minutes."""
    global running
    running = True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    signal.signal(signal.SIGINT, stop_scheduler)
    signal.signal(signal.SIGTERM, stop_scheduler)

    logger.info(
        "Grievance escalation scheduler started. Interval: %s seconds.",
        INTERVAL_SECONDS,
    )

    try:
        while running:
            try:
                with app.app_context():
                    escalated_count = escalate_overdue_grievances()

                logger.info(
                    "Escalation cycle completed. Grievances escalated: %s",
                    escalated_count,
                )

            except Exception:
                logger.exception("Unexpected error during escalation cycle.")

            if running:
                # Sleep in short intervals so shutdown signals are noticed.
                remaining = INTERVAL_SECONDS

                while running and remaining > 0:
                    sleep_time = min(1, remaining)
                    time.sleep(sleep_time)
                    remaining -= sleep_time

    finally:
        logger.info("Grievance escalation scheduler stopped.")


if __name__ == "__main__":
    run_scheduler()
