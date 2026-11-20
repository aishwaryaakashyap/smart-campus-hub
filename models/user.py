from datetime import datetime

from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = 'users'

    # Supported account states
    STATUS_ACTIVE = 'active'
    STATUS_PENDING = 'pending'
    STATUS_REJECTED = 'rejected'
    STATUS_DEACTIVATED = 'deactivated'

    # Supported application roles
    ROLE_STUDENT = 'student'
    ROLE_ADVISOR = 'advisor'
    ROLE_COORDINATOR = 'coordinator'
    ROLE_CHAIRPERSON = 'chairperson'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        nullable=False
    )

    # Existing accounts remain active by default.
    # New registrations must explicitly use pending status.
    account_status = db.Column(
        db.String(20),
        nullable=False,
        default=STATUS_ACTIVE,
        server_default='active',
        index=True
    )

    # Institutional email verification timestamp.
    email_verified_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # Records the Coordinator or Advisor who reviewed the account.
    reviewed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'users.id',
            ondelete='SET NULL'
        ),
        nullable=True,
        index=True
    )

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    rejection_reason = db.Column(
        db.String(500),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Self-referential relationship for account review history.
    reviewed_by = db.relationship(
        'User',
        remote_side=[id],
        foreign_keys=[reviewed_by_user_id],
        backref=db.backref(
            'reviewed_accounts',
            lazy='select'
        )
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
