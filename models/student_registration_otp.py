from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StudentRegistrationOTP(db.Model):
    __tablename__ = "student_registration_otps"

    __table_args__ = (
        db.Index("idx_student_otp_user_created", "user_id", "created_at"),
        db.Index("idx_student_otp_expires", "expires_at"),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Store only the SHA-256 hash, never the original OTP.
    otp_hash = db.Column(
        db.String(64),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    used_at = db.Column(
        db.DateTime,
        nullable=True
    )

    user = db.relationship(
        "User",
        backref=db.backref("registration_otps", lazy=True)
    )

    def __repr__(self):
        return f"<StudentRegistrationOTP {self.id}: user={self.user_id}>"
