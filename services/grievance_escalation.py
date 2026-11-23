import logging
from datetime import datetime, timezone

from extensions import db
from models import (
    ChairpersonSettings,
    Grievance,
    GrievanceEscalation,
    User,
)
from services.notifications import create_notification
from services.activity_log import record_activity


logger = logging.getLogger(__name__)


def _normalise_datetime(value):
    """Convert an aware datetime to naive UTC for database comparisons."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


def escalate_overdue_grievances(now=None):
    """
    Escalate overdue Advisor grievances directly to the active primary
    Chairperson.

    Each grievance is locked, rechecked and committed independently.
    Returns the number of successfully escalated grievances.
    """
    current_time = _normalise_datetime(
        now or datetime.now(timezone.utc)
    )

    settings = (
        ChairpersonSettings.query
        .filter_by(singleton_id=1)
        .one_or_none()
    )

    if not settings or not settings.primary_chairperson_user_id:
        logger.warning(
            "Grievance escalation skipped: no primary Chairperson configured."
        )
        return 0

    chairperson = db.session.get(
        User,
        settings.primary_chairperson_user_id
    )

    if (
        not chairperson
        or chairperson.role != User.ROLE_CHAIRPERSON
        or chairperson.account_status != User.STATUS_ACTIVE
    ):
        logger.warning(
            "Grievance escalation skipped: configured primary Chairperson "
            "is missing, inactive, or has an invalid role."
        )
        return 0

    candidate_ids = [
        grievance_id
        for (grievance_id,) in (
            db.session.query(Grievance.id)
            .filter(
                Grievance.sla_due_at.isnot(None),
                Grievance.sla_due_at <= current_time,
                Grievance.current_handler_id.isnot(None),
                Grievance.current_handler_role == User.ROLE_ADVISOR,
                Grievance.escalation_level == 0,
                Grievance.status.notin_(("Resolved", "Rejected"))
            )
            .order_by(Grievance.sla_due_at.asc(), Grievance.id.asc())
            .all()
        )
    ]

    escalated_count = 0

    for grievance_id in candidate_ids:
        try:
            grievance = (
                Grievance.query
                .filter_by(id=grievance_id)
                .with_for_update()
                .one_or_none()
            )

            if not grievance:
                db.session.rollback()
                continue

            # Recheck eligibility after acquiring the row lock.
            if (
                grievance.sla_due_at is None
                or grievance.sla_due_at > current_time
                or grievance.current_handler_id is None
                or grievance.current_handler_role != User.ROLE_ADVISOR
                or grievance.escalation_level != 0
                or grievance.status in ("Resolved", "Rejected")
            ):
                db.session.rollback()
                continue

            # Preserve the original Advisor assignment for audit purposes.
            previous_advisor_id = grievance.current_handler_id
            original_deadline = grievance.sla_due_at

            grievance.current_handler_id = chairperson.id
            grievance.current_handler_role = User.ROLE_CHAIRPERSON
            grievance.escalation_level = 1
            grievance.last_escalated_at = current_time
            grievance.sla_due_at = None

            escalation = GrievanceEscalation(
                grievance_id=grievance.id,
                from_user_id=previous_advisor_id,
                to_user_id=chairperson.id,
                from_role=User.ROLE_ADVISOR,
                to_role=User.ROLE_CHAIRPERSON,
                escalation_level=1,
                reason=(
                    "Automatically escalated because the fixed "
                    "four-working-day Advisor SLA expired without resolution."
                ),
                sla_due_at=original_deadline,
                escalated_at=current_time,
                triggered_by_user_id=None
            )

            db.session.add(escalation)

            record_activity(
                actor_user_id=None,
                target_user_id=chairperson.id,
                action="grievance_escalated",
                entity_type="grievance",
                entity_id=grievance.id,
                description=(
                    f"Automatically escalated grievance {grievance.id} "
                    f"from Advisor {previous_advisor_id} "
                    f"to Chairperson {chairperson.id}"
                )
            )

            create_notification(
                user_id=chairperson.id,
                title="Grievance Escalated to You",
                message=(
                    f'Grievance "{grievance.title}" '
                    "has been escalated to you because the Advisor "
                    "SLA expired without resolution."
                ),
                notification_type="grievance"
            )

            db.session.commit()
            escalated_count += 1

            logger.info(
                "Grievance %s escalated from Advisor %s to Chairperson %s.",
                grievance.id,
                previous_advisor_id,
                chairperson.id
            )

        except Exception:
            db.session.rollback()
            logger.exception(
                "Failed to escalate grievance %s.",
                grievance_id
            )

    return escalated_count
