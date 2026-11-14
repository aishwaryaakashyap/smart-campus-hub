
from datetime import datetime
from sqlalchemy import Index
from sqlalchemy.dialects.mysql import INTEGER, TINYINT
from extensions import db


class Grievance(db.Model):
    __tablename__ = 'grievances'

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('students.id'),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey('grievance_categories.id'),
        nullable=False
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))

    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(30), default='Submitted')

    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey('users.id')
    )

    # Phase 16: SLA and current-handler tracking.
    current_handler_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    current_handler_role = db.Column(db.String(30), nullable=True)
    sla_due_at = db.Column(db.DateTime, nullable=True)

    escalation_level = db.Column(
        TINYINT(unsigned=True),
        nullable=False,
        default=0,
        server_default=db.text("0")
    )

    last_escalated_at = db.Column(db.DateTime, nullable=True)
    resolution_confirmed_at = db.Column(db.DateTime, nullable=True)

    reopen_count = db.Column(
        INTEGER(unsigned=True),
        nullable=False,
        default=0,
        server_default=db.text("0")
    )

    __table_args__ = (
        Index("idx_grievances_current_handler", "current_handler_id"),
        Index("idx_grievances_sla_due", "sla_due_at"),
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    student = db.relationship(
        'Student',
        backref=db.backref('grievances', lazy=True)
    )

    category = db.relationship(
        'GrievanceCategory',
        backref=db.backref('grievances', lazy=True)
    )

    advisor = db.relationship(
        'User',
        foreign_keys=[assigned_to],
        backref=db.backref('assigned_grievances', lazy=True)
    )

    current_handler = db.relationship(
        'User',
        foreign_keys=[current_handler_id]
    )

    def __repr__(self):
        return f'<Grievance {self.id}: {self.title}>'


class GrievanceUpdate(db.Model):
    __tablename__ = 'grievance_updates'

    id = db.Column(db.Integer, primary_key=True)

    grievance_id = db.Column(
        db.Integer,
        db.ForeignKey('grievances.id'),
        nullable=False
    )

    updated_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    old_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    grievance = db.relationship(
        'Grievance',
        backref=db.backref('updates', lazy=True)
    )


class GrievanceEscalation(db.Model):
    __tablename__ = 'grievance_escalations'

    __table_args__ = (
        Index(
            "idx_grievance_escalations_grievance_time",
            "grievance_id",
            "escalated_at"
        ),
        Index(
            "idx_grievance_escalations_to_user",
            "to_user_id"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    grievance_id = db.Column(
        db.Integer,
        db.ForeignKey('grievances.id'),
        nullable=False
    )

    from_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    to_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False
    )

    from_role = db.Column(db.String(30), nullable=True)
    to_role = db.Column(db.String(30), nullable=False)

    escalation_level = db.Column(
        TINYINT(unsigned=True),
        nullable=False
    )
    reason = db.Column(db.String(500), nullable=False)
    sla_due_at = db.Column(db.DateTime, nullable=True)

    escalated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=db.func.current_timestamp()
    )

    triggered_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    grievance = db.relationship(
        'Grievance',
        backref=db.backref('escalation_events', lazy=True)
    )

    from_user = db.relationship(
        'User',
        foreign_keys=[from_user_id]
    )

    to_user = db.relationship(
        'User',
        foreign_keys=[to_user_id]
    )

    triggered_by = db.relationship(
        'User',
        foreign_keys=[triggered_by_user_id]
    )

    def __repr__(self):
        return (
            f'<GrievanceEscalation {self.id}: '
            f'grievance={self.grievance_id}, '
            f'level={self.escalation_level}>'
        )
