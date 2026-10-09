
from models import Notification
from extensions import db


def create_notification(user_id, title, message, notification_type):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type
    )

    db.session.add(notification)

    return notification
