from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.mysql import TINYINT

from extensions import db


class ChairpersonSettings(db.Model):
    """
    Institution-wide Chairperson configuration.

    The singleton primary key and CHECK constraint ensure
    that the application has only one settings record.
    """

    __tablename__ = "chairperson_settings"

    __table_args__ = (
        CheckConstraint(
            "singleton_id = 1",
            name="ck_chairperson_settings_singleton"
        ),
    )

    singleton_id = db.Column(
        db.SmallInteger().with_variant(
            TINYINT(unsigned=True),
            "mysql"
        ),
        primary_key=True,
        nullable=False,
        default=1,
        server_default="1"
    )

    primary_chairperson_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        unique=True
    )

    updated_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp()
    )

    primary_chairperson = db.relationship(
        "User",
        foreign_keys=[primary_chairperson_user_id]
    )

    updated_by = db.relationship(
        "User",
        foreign_keys=[updated_by_user_id]
    )

    def __repr__(self):
        return (
            "<ChairpersonSettings "
            f"primary={self.primary_chairperson_user_id}>"
        )
