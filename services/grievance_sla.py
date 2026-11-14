import os
from datetime import datetime, timedelta, timezone


DEFAULT_SLA_HOURS = {
    "High": 24,
    "Medium": 48,
    "Low": 72,
}


def get_sla_hours(priority):
    if priority not in DEFAULT_SLA_HOURS:
        raise ValueError("Invalid grievance priority")

    environment_key = f"GRIEVANCE_SLA_{priority.upper()}_HOURS"

    raw_value = os.environ.get(
        environment_key,
        str(DEFAULT_SLA_HOURS[priority])
    )

    try:
        hours = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{environment_key} must be a positive integer"
        ) from error

    if hours <= 0:
        raise ValueError(
            f"{environment_key} must be a positive integer"
        )

    return hours


def calculate_sla_due_at(priority, now=None):
    start_time = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return start_time + timedelta(hours=get_sla_hours(priority))
