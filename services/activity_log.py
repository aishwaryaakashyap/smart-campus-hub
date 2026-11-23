from extensions import db
from models.activity_log import ActivityLog


def record_activity(
    actor_user_id,
    action,
    entity_type,
    entity_id,
    description,
    target_user_id=None
):
    """Add an activity record to the current database transaction."""
    activity = ActivityLog(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description
    )

    db.session.add(activity)
    return activity
