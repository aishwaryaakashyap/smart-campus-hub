import os
from datetime import date, datetime, timedelta, timezone


GRIEVANCE_SLA_WORKING_DAYS = 4
VALID_PRIORITIES = ("High", "Medium", "Low")


def get_sla_working_days(priority):
    """Return the fixed four-working-day SLA for every valid priority."""
    if priority not in VALID_PRIORITIES:
        raise ValueError("Invalid grievance priority")

    return GRIEVANCE_SLA_WORKING_DAYS


def get_public_holidays():
    """Read configured public holidays from YYYY-MM-DD environment values."""
    raw_dates = os.environ.get("GRIEVANCE_PUBLIC_HOLIDAYS", "")
    holidays = set()

    for value in raw_dates.split(","):
        value = value.strip()
        if value:
            try:
                holidays.add(date.fromisoformat(value))
            except ValueError as exc:
                raise ValueError(
                    "GRIEVANCE_PUBLIC_HOLIDAYS must contain YYYY-MM-DD dates"
                ) from exc

    return holidays


def calculate_sla_due_at(priority, now=None, public_holidays=None):
    """Calculate four working days after the start, excluding weekends/holidays."""
    remaining_days = get_sla_working_days(priority)
    start_time = now or datetime.now(timezone.utc).replace(tzinfo=None)
    holidays = (
        get_public_holidays()
        if public_holidays is None
        else set(public_holidays)
    )

    deadline = start_time

    while remaining_days:
        deadline += timedelta(days=1)

        if deadline.weekday() < 5 and deadline.date() not in holidays:
            remaining_days -= 1

    return deadline
