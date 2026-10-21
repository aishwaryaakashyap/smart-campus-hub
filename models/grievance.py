from extensions import db
from datetime import datetime


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
