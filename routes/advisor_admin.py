import hashlib
import re
import secrets

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session, url_for
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from services.record_deletion_guard import find_referencing_records
from models import AcademicClass, PasswordResetToken, Student, User
from routes.academic_admin import require_coordinator
from services.email_service import send_account_setup_email
from services.notifications import create_notification


advisor_admin_bp = Blueprint("advisor_admin", __name__)


def get_advisor_account(advisor_id):
    """Load an account and ensure that it is an Advisor."""
    advisor = db.session.get(User, advisor_id)

    if not advisor or advisor.role != User.ROLE_ADVISOR:
        return None

    return advisor


def serialize_advisor_account(advisor):
    """Serialize Advisor account and latest review details."""
    reviewer = advisor.reviewed_by

    return {
        "id": advisor.id,
        "name": advisor.name,
        "email": advisor.email,
        "role": advisor.role,
        "account_status": advisor.account_status,
        "created_at": (
            advisor.created_at.isoformat()
            if advisor.created_at else None
        ),
        "reviewed_by_user_id": advisor.reviewed_by_user_id,
        "reviewed_by_name": reviewer.name if reviewer else None,
        "reviewed_at": (
            advisor.reviewed_at.isoformat()
            if advisor.reviewed_at else None
        ),
        "rejection_reason": advisor.rejection_reason
    }


def invalidate_unused_setup_tokens(advisor_id):
    """Invalidate outstanding password setup/reset tokens."""
    PasswordResetToken.query.filter(
        PasswordResetToken.user_id == advisor_id,
        PasswordResetToken.used_at.is_(None)
    ).delete(synchronize_session=False)


def create_setup_token(advisor):
    """Create a hashed, expiring, single-use password setup token."""
    invalidate_unused_setup_tokens(advisor.id)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    expiry_minutes = current_app.config.get(
        "PASSWORD_RESET_TOKEN_MINUTES",
        15
    )

    if (
        isinstance(expiry_minutes, bool)
        or not isinstance(expiry_minutes, int)
        or expiry_minutes < 1
    ):
        expiry_minutes = 15

    token_record = PasswordResetToken(
        user_id=advisor.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(minutes=expiry_minutes)
    )

    db.session.add(token_record)

    return raw_token, expiry_minutes


def send_setup_link(advisor, raw_token, expiry_minutes):
    """Send the setup link without exposing the raw token in an API response."""
    base_url = current_app.config.get("APP_BASE_URL", "").rstrip("/")

    if not base_url:
        current_app.logger.error(
            "Cannot send Advisor setup email: APP_BASE_URL is not configured."
        )
        return False

    setup_url = (
        f"{base_url}"
        f"{url_for('password_reset.reset_password_page')}"
        f"#token={raw_token}"
    )

    try:
        send_account_setup_email(
            advisor.email,
            setup_url,
            expiry_minutes
        )
        return True

    except Exception:
        current_app.logger.exception(
            "Advisor account setup email could not be delivered."
        )
        return False


@advisor_admin_bp.route("/advisors/accounts", methods=["GET"])
def list_advisor_accounts():
    """List Advisor accounts, optionally filtered by account status."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    status = request.args.get("status", "all").strip().lower()

    valid_statuses = {
        "all",
        User.STATUS_PENDING,
        User.STATUS_ACTIVE,
        User.STATUS_REJECTED,
        User.STATUS_DEACTIVATED
    }

    if status not in valid_statuses:
        return jsonify({
            "error": "Invalid account status filter"
        }), 400

    query = User.query.filter_by(role=User.ROLE_ADVISOR)

    if status != "all":
        query = query.filter_by(account_status=status)

    accounts = query.order_by(User.name.asc()).all()

    return jsonify({
        "accounts": [
            serialize_advisor_account(account)
            for account in accounts
        ],
        "total": len(accounts)
    }), 200


@advisor_admin_bp.route("/advisors", methods=["POST"])
def create_advisor_account():
    """Create an Advisor account in pending status."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A valid JSON object is required"
        }), 400

    name = data.get("name")
    email = data.get("email")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "A valid name is required"}), 400

    if not isinstance(email, str):
        return jsonify({"error": "A valid email address is required"}), 400

    name = name.strip()
    email = email.strip().lower()

    if len(name) > 100:
        return jsonify({
            "error": "Name must be 100 characters or fewer"
        }), 400

    if (
        len(email) > 120
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
    ):
        return jsonify({
            "error": "A valid email address is required"
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            "error": "This email address is already registered"
        }), 409

    advisor = User(
        name=name,
        email=email,
        role=User.ROLE_ADVISOR,
        account_status=User.STATUS_PENDING
    )

    # The random initial password is never returned or disclosed.
    advisor.set_password(secrets.token_urlsafe(32))

    try:
        db.session.add(advisor)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This email address is already registered"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to create Advisor account at this time"
        }), 500

    return jsonify({
        "message": "Advisor account created and is awaiting approval",
        "advisor": serialize_advisor_account(advisor)
    }), 201


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/approve",
    methods=["POST"]
)
def approve_advisor_account(advisor_id):
    """Approve a pending Advisor and issue a password setup link."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if not advisor:
        return jsonify({"error": "Advisor account not found"}), 404

    if advisor.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending Advisor accounts can be approved"
        }), 409

    raw_token, expiry_minutes = create_setup_token(advisor)

    advisor.account_status = User.STATUS_ACTIVE
    advisor.reviewed_by_user_id = session["user_id"]
    advisor.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    advisor.rejection_reason = None

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to approve Advisor account at this time"
        }), 500

    email_sent = send_setup_link(
        advisor,
        raw_token,
        expiry_minutes
    )

    if not email_sent:
        return jsonify({
            "message": (
                "Advisor approved, but the setup email could not be sent. "
                "Use the resend setup email action."
            ),
            "email_sent": False,
            "advisor": serialize_advisor_account(advisor)
        }), 202

    return jsonify({
        "message": "Advisor approved and setup email sent",
        "email_sent": True,
        "advisor": serialize_advisor_account(advisor)
    }), 200


def read_optional_review_reason():
    """Validate an optional review or deactivation reason."""
    data = request.get_json(silent=True)

    if data is None:
        data = {}

    if not isinstance(data, dict):
        return None, (jsonify({
            "error": "A valid JSON object is required"
        }), 400)

    reason = data.get("reason")

    if reason is not None and not isinstance(reason, str):
        return None, (jsonify({
            "error": "Reason must be text"
        }), 400)

    if reason is not None:
        reason = reason.strip() or None

        if reason and len(reason) > 500:
            return None, (jsonify({
                "error": "Reason must be 500 characters or fewer"
            }), 400)

    return reason, None


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/reject",
    methods=["POST"]
)
def reject_advisor_account(advisor_id):
    """Reject a pending Advisor account and record the review."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if not advisor:
        return jsonify({"error": "Advisor account not found"}), 404

    if advisor.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending Advisor accounts can be rejected"
        }), 409

    reason, error = read_optional_review_reason()

    if error:
        return error

    advisor.account_status = User.STATUS_REJECTED
    advisor.reviewed_by_user_id = session["user_id"]
    advisor.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    advisor.rejection_reason = reason

    try:
        invalidate_unused_setup_tokens(advisor.id)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to reject Advisor account at this time"
        }), 500

    return jsonify({
        "message": "Advisor account rejected",
        "advisor": serialize_advisor_account(advisor)
    }), 200


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/deactivate",
    methods=["POST"]
)
def deactivate_advisor_account(advisor_id):
    """Deactivate an Advisor without deleting linked records."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if not advisor:
        return jsonify({"error": "Advisor account not found"}), 404

    if advisor.account_status != User.STATUS_ACTIVE:
        return jsonify({
            "error": "Only active Advisor accounts can be deactivated"
        }), 409

    advisor.account_status = User.STATUS_DEACTIVATED
    advisor.reviewed_by_user_id = session["user_id"]
    advisor.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Do not overwrite rejection_reason during deactivation.

    try:
        invalidate_unused_setup_tokens(advisor.id)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to deactivate Advisor account at this time"
        }), 500

    return jsonify({
        "message": (
            "Advisor deactivated. Existing class assignments and "
            "grievance records have been preserved."
        ),
        "advisor": serialize_advisor_account(advisor)
    }), 200


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/reactivate",
    methods=["POST"]
)
def reactivate_advisor_account(advisor_id):
    """Reactivate a previously deactivated Advisor."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if not advisor:
        return jsonify({"error": "Advisor account not found"}), 404

    if advisor.account_status != User.STATUS_DEACTIVATED:
        return jsonify({
            "error": "Only deactivated Advisor accounts can be reactivated"
        }), 409

    advisor.account_status = User.STATUS_ACTIVE
    advisor.reviewed_by_user_id = session["user_id"]
    advisor.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    advisor.rejection_reason = None

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to reactivate Advisor account at this time"
        }), 500

    return jsonify({
        "message": "Advisor account reactivated successfully",
        "advisor": serialize_advisor_account(advisor)
    }), 200


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/setup-email",
    methods=["POST"]
)
def resend_advisor_setup_email(advisor_id):
    """Generate and send a fresh password setup/reset link."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if not advisor:
        return jsonify({"error": "Advisor account not found"}), 404

    if advisor.account_status != User.STATUS_ACTIVE:
        return jsonify({
            "error": "Setup email can only be sent to active Advisors"
        }), 409

    raw_token, expiry_minutes = create_setup_token(advisor)

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to prepare Advisor setup email"
        }), 500

    email_sent = send_setup_link(
        advisor,
        raw_token,
        expiry_minutes
    )

    if not email_sent:
        return jsonify({
            "message": "Setup email could not be sent. Check email configuration.",
            "email_sent": False
        }), 202

    return jsonify({
        "message": "Advisor setup email sent successfully",
        "email_sent": True
    }), 200


@advisor_admin_bp.route(
    "/advisors/<int:advisor_id>/delete",
    methods=["POST"]
)
def delete_advisor_account(advisor_id):
    """
    Permanently delete a deactivated Advisor only when no
    institutional records depend on the account.
    """
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError

    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisor = get_advisor_account(advisor_id)

    if advisor is None:
        return jsonify({
            "error": "Advisor account not found"
        }), 404

    if advisor.account_status != User.STATUS_DEACTIVATED:
        return jsonify({
            "error": (
                "Only deactivated Advisor accounts can be permanently "
                "deleted. Deactivate the account first."
            )
        }), 409

    try:
        # Password reset tokens are temporary authentication data.
        # Remove them only as part of a successful account deletion.
        references = find_referencing_records(
            User.__tablename__,
            advisor_id,
            exclude_tables={"password_reset_tokens"}
        )

        if references:
            return jsonify({
                "error": (
                    "This Advisor is linked to institutional records and "
                    "cannot be deleted. Existing class assignments, "
                    "grievances, notifications and review history must "
                    "be preserved."
                ),
                "references": references
            }), 409

        PasswordResetToken.query.filter_by(
            user_id=advisor_id
        ).delete(synchronize_session=False)

        db.session.delete(advisor)
        db.session.commit()

        return jsonify({
            "message": "Deactivated Advisor account permanently deleted.",
            "deleted_id": advisor_id
        }), 200

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": (
                "Deletion was blocked by a database relationship. "
                "The Advisor account has not been deleted."
            )
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "A database error prevented Advisor deletion."
        }), 500



# ============================================================
# Student registration review by assigned Advisors
# ============================================================

def require_current_advisor():
    """Validate the session against the current active Advisor account."""
    user_id = session.get("user_id")

    if not user_id:
        return None, (jsonify({"error": "Not logged in"}), 401)

    session_role = session.get("role")
    advisor = db.session.get(User, user_id)

    if not advisor or advisor.role != session_role:
        session.clear()
        return None, (jsonify({"error": "Not logged in"}), 401)

    if advisor.account_status != User.STATUS_ACTIVE:
        session.clear()
        return None, (jsonify({"error": "Account is not active"}), 401)

    if advisor.role != User.ROLE_ADVISOR:
        return None, (
            jsonify({"error": "Only Advisors can review student registrations"}),
            403
        )

    return advisor, None


def get_assigned_pending_student(student_id, advisor_id):
    """Find a student only if their active class belongs to this Advisor."""
    return (
        db.session.query(Student)
        .join(User, Student.user_id == User.id)
        .join(
            AcademicClass,
            Student.academic_class_id == AcademicClass.id
        )
        .filter(
            Student.id == student_id,
            AcademicClass.advisor_user_id == advisor_id,
            AcademicClass.is_active.is_(True)
        )
        .first()
    )


def serialize_student_registration(student):
    """Return safe student registration details for the Advisor dashboard."""
    user = student.user
    academic_class = student.academic_class

    return {
        "student_id": student.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "register_number": student.register_number,
        "course": student.course,
        "branch": student.branch,
        "semester": student.semester,
        "cgpa": student.cgpa,
        "phone": student.phone,
        "graduation_year": student.graduation_year,
        "academic_class": {
            "id": academic_class.id,
            "course": academic_class.course,
            "branch": academic_class.branch,
            "section": academic_class.section,
            "admission_year": academic_class.admission_year
        },
        "registered_at": (
            user.created_at.isoformat()
            if user.created_at else None
        ),
        "email_verified_at": (
            user.email_verified_at.isoformat()
            if user.email_verified_at else None
        )
    }


@advisor_admin_bp.route(
    "/students/registrations",
    methods=["GET"]
)
def list_pending_student_registrations():
    """List verified pending students in this Advisor's active classes."""
    advisor, auth_error = require_current_advisor()

    if auth_error:
        return auth_error

    students = (
        db.session.query(Student)
        .join(User, Student.user_id == User.id)
        .join(
            AcademicClass,
            Student.academic_class_id == AcademicClass.id
        )
        .filter(
            AcademicClass.advisor_user_id == advisor.id,
            AcademicClass.is_active.is_(True),
            User.role == User.ROLE_STUDENT,
            User.account_status == User.STATUS_PENDING,
            User.email_verified_at.isnot(None)
        )
        .order_by(User.created_at.asc(), User.id.asc())
        .all()
    )

    return jsonify({
        "students": [
            serialize_student_registration(student)
            for student in students
        ],
        "total": len(students)
    }), 200


@advisor_admin_bp.route(
    "/students/<int:student_id>/approve",
    methods=["POST"]
)
def approve_student_registration(student_id):
    """Approve a verified student assigned to the current Advisor."""
    advisor, auth_error = require_current_advisor()

    if auth_error:
        return auth_error

    student = get_assigned_pending_student(student_id, advisor.id)

    if not student:
        return jsonify({
            "error": "Student registration not found in your assigned classes"
        }), 404

    user = student.user

    if user.role != User.ROLE_STUDENT:
        return jsonify({"error": "This account is not a student"}), 409

    if user.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending student registrations can be approved"
        }), 409

    if not user.email_verified_at:
        return jsonify({
            "error": "Student must verify their email before approval"
        }), 409

    user.account_status = User.STATUS_ACTIVE
    user.reviewed_by_user_id = advisor.id
    user.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.rejection_reason = None

    try:
        create_notification(
            user.id,
            "Student registration approved",
            "Your Smart Campus Hub registration has been approved. "
            "You can now log in to your account.",
            "student_registration"
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to approve student registration at this time"
        }), 500

    return jsonify({
        "message": "Student registration approved successfully",
        "student": {
            "student_id": student.id,
            "name": user.name,
            "account_status": user.account_status
        }
    }), 200


@advisor_admin_bp.route(
    "/students/<int:student_id>/reject",
    methods=["POST"]
)
def reject_student_registration(student_id):
    """Reject a verified student assigned to the current Advisor."""
    advisor, auth_error = require_current_advisor()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if data is None:
        data = {}

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON object is required"}), 400

    reason = data.get("reason")

    if reason is not None and not isinstance(reason, str):
        return jsonify({"error": "Rejection reason must be text"}), 400

    if reason is not None:
        reason = reason.strip() or None

        if reason and len(reason) > 500:
            return jsonify({
                "error": "Rejection reason must be 500 characters or fewer"
            }), 400

    student = get_assigned_pending_student(student_id, advisor.id)

    if not student:
        return jsonify({
            "error": "Student registration not found in your assigned classes"
        }), 404

    user = student.user

    if user.role != User.ROLE_STUDENT:
        return jsonify({"error": "This account is not a student"}), 409

    if user.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending student registrations can be rejected"
        }), 409

    if not user.email_verified_at:
        return jsonify({
            "error": "Student must verify their email before rejection"
        }), 409

    user.account_status = User.STATUS_REJECTED
    user.reviewed_by_user_id = advisor.id
    user.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.rejection_reason = reason

    try:
        create_notification(
            user.id,
            "Student registration update",
            (
                "Your Smart Campus Hub registration was not approved."
                + (f" Reason: {reason}" if reason else "")
            ),
            "student_registration"
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to reject student registration at this time"
        }), 500

    return jsonify({
        "message": "Student registration rejected",
        "student": {
            "student_id": student.id,
            "name": user.name,
            "account_status": user.account_status,
            "rejection_reason": user.rejection_reason
        }
    }), 200
