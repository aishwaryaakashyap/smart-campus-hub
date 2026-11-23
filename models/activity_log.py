from datetime import datetime

from extensions import db


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)

    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    target_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    action = db.Column(
        db.String(80),
        nullable=False,
        index=True
    )

    entity_type = db.Column(
        db.String(50),
        nullable=False
    )

    entity_id = db.Column(
        db.Integer,
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )

    actor = db.relationship(
        'User',
        foreign_keys=[actor_user_id]
    )

    target_user = db.relationship(
        'User',
        foreign_keys=[target_user_id]
    )

    def __repr__(self):
        return (
            f'<ActivityLog {self.id}: '
            f'{self.action} ({self.entity_type}:{self.entity_id})>'
        )
