from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from extensions import db


class AcademicClass(db.Model):
    """
    Represents an academic class/section for a particular admission batch.

    Example:
        Course: BCA
        Branch: CSE
        Section: A
        Admission Year: 2024
    """

    __tablename__ = "academic_classes"

    __table_args__ = (
        UniqueConstraint(
            "course",
            "branch",
            "section",
            "admission_year",
            name="uq_academic_class_identity"
        ),
        Index(
            "idx_academic_classes_advisor",
            "advisor_user_id"
        ),
        Index(
            "idx_academic_classes_active",
            "is_active"
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    course = db.Column(
        db.String(50),
        nullable=False
    )

    branch = db.Column(
        db.String(50),
        nullable=False
    )

    section = db.Column(
        db.String(20),
        nullable=False
    )

    admission_year = db.Column(
        db.Integer,
        nullable=False
    )

    advisor_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL"
        ),
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default="1"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # One class has one assigned advisor at a time.
    # An advisor can handle multiple classes.
    advisor = db.relationship(
        "User",
        backref=db.backref(
            "advised_classes",
            lazy="select"
        ),
        foreign_keys=[advisor_user_id]
    )

    def __repr__(self):
        return (
            f"<AcademicClass "
            f"{self.course}/{self.branch}/"
            f"{self.section}/{self.admission_year}>"
        )
