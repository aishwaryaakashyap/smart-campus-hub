from datetime import datetime, timezone

from extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Store only the SHA-256 hash, never the original reset token.
    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        index=True
    )

    used_at = db.Column(
        db.DateTime,
        nullable=True
    )

    user = db.relationship(
        "User",
        backref=db.backref("password_reset_tokens", lazy=True)
    )

    def __repr__(self):
        return f"<PasswordResetToken {self.id}: user={self.user_id}>"
