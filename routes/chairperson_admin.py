import hashlib
import re
import secrets

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session, url_for
from sqlalchemy import MetaData, Table, func, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import ChairpersonSettings, PasswordResetToken, User
from routes.academic_admin import require_coordinator
from services.email_service import send_account_setup_email


chairperson_admin_bp = Blueprint(
    "chairperson_admin",
    __name__
)


def get_chairperson_account(chairperson_id):
    """Load a user and verify that the account is a Chairperson."""
    chairperson = db.session.get(User, chairperson_id)

    if not chairperson or chairperson.role != User.ROLE_CHAIRPERSON:
        return None

    return chairperson


def serialize_chairperson(chairperson, primary_user_id=None):
    """Return safe Chairperson information for Coordinator management."""
    reviewer = chairperson.reviewed_by

    return {
        "id": chairperson.id,
        "name": chairperson.name,
        "email": chairperson.email,
        "role": chairperson.role,
        "account_status": chairperson.account_status,
        "is_primary": chairperson.id == primary_user_id,
        "created_at": (
            chairperson.created_at.isoformat()
            if chairperson.created_at else None
        ),
        "reviewed_by_user_id": chairperson.reviewed_by_user_id,
        "reviewed_by_name": reviewer.name if reviewer else None,
        "reviewed_at": (
            chairperson.reviewed_at.isoformat()
            if chairperson.reviewed_at else None
        ),
        "rejection_reason": chairperson.rejection_reason
    }


def get_primary_settings(lock=False):
    """Load the institution-wide singleton settings record."""
    query = ChairpersonSettings.query.filter_by(singleton_id=1)

    if lock:
        query = query.with_for_update()

    return query.one_or_none()


def invalidate_chairperson_setup_tokens(chairperson_id):
    """Invalidate previous unused setup/reset tokens."""
    PasswordResetToken.query.filter(
        PasswordResetToken.user_id == chairperson_id,
        PasswordResetToken.used_at.is_(None)
    ).delete(synchronize_session=False)


def create_chairperson_setup_token(chairperson):
    """Create a hashed, single-use password setup token."""
    invalidate_chairperson_setup_tokens(chairperson.id)

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
        user_id=chairperson.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(minutes=expiry_minutes)
    )

    db.session.add(token_record)

    return raw_token, expiry_minutes


def send_chairperson_setup_link(chairperson, raw_token, expiry_minutes):
    """Send a Chairperson-specific setup email."""
    base_url = current_app.config.get(
        "APP_BASE_URL",
        ""
    ).rstrip("/")

    if not base_url:
        current_app.logger.error(
            "Chairperson setup email unavailable: APP_BASE_URL is missing."
        )
        return False

    setup_url = (
        f"{base_url}"
        f"{url_for('password_reset.reset_password_page')}"
        f"#token={raw_token}"
    )

    try:
        send_account_setup_email(
            chairperson.email,
            setup_url,
            expiry_minutes,
            account_label="Chairperson"
        )
        return True

    except Exception:
        current_app.logger.exception(
            "Chairperson setup email delivery failed."
        )
        return False


def read_chairperson_rejection_reason():
    """Validate an optional rejection reason."""
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


@chairperson_admin_bp.route("/chairpersons", methods=["GET"])
def list_chairpersons():
    """List Chairperson accounts and the institution's primary selection."""
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

    settings = get_primary_settings()

    if settings is None:
        return jsonify({
            "error": "Chairperson settings are not initialized"
        }), 503

    primary_user_id = settings.primary_chairperson_user_id

    query = User.query.filter_by(
        role=User.ROLE_CHAIRPERSON
    )

    if status != "all":
        query = query.filter_by(account_status=status)

    accounts = query.order_by(User.name.asc()).all()

    return jsonify({
        "chairpersons": [
            serialize_chairperson(account, primary_user_id)
            for account in accounts
        ],
        "total": len(accounts),
        "primary_chairperson_user_id": primary_user_id
    }), 200


@chairperson_admin_bp.route("/chairpersons", methods=["POST"])
def create_chairperson():
    """Create a pending Chairperson account."""
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
        return jsonify({
            "error": "A valid name is required"
        }), 400

    if not isinstance(email, str):
        return jsonify({
            "error": "A valid email address is required"
        }), 400

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

    chairperson = User(
        name=name,
        email=email,
        role=User.ROLE_CHAIRPERSON,
        account_status=User.STATUS_PENDING
    )

    # The random initial password is never returned to the Coordinator.
    chairperson.set_password(secrets.token_urlsafe(32))

    try:
        db.session.add(chairperson)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This email address is already registered"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to create Chairperson account at this time"
        }), 500

    return jsonify({
        "message": "Chairperson account created and is awaiting approval",
        "chairperson": serialize_chairperson(chairperson)
    }), 201


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/approve",
    methods=["POST"]
)
def approve_chairperson(chairperson_id):
    """Approve a pending Chairperson and send a password setup link."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending Chairperson accounts can be approved"
        }), 409

    settings = get_primary_settings()

    if settings is None:
        return jsonify({
            "error": "Chairperson settings are not initialized"
        }), 503

    raw_token, expiry_minutes = create_chairperson_setup_token(chairperson)

    chairperson.account_status = User.STATUS_ACTIVE
    chairperson.reviewed_by_user_id = session["user_id"]
    chairperson.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    chairperson.rejection_reason = None

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to approve Chairperson account at this time"
        }), 500

    email_sent = send_chairperson_setup_link(
        chairperson,
        raw_token,
        expiry_minutes
    )

    if not email_sent:
        return jsonify({
            "message": (
                "Chairperson approved, but the setup email could not be sent. "
                "Use the resend setup email action."
            ),
            "email_sent": False,
            "chairperson": serialize_chairperson(
                chairperson,
                settings.primary_chairperson_user_id
            )
        }), 202

    return jsonify({
        "message": "Chairperson approved and setup email sent",
        "email_sent": True,
        "chairperson": serialize_chairperson(
            chairperson,
            settings.primary_chairperson_user_id
        )
    }), 200


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/reject",
    methods=["POST"]
)
def reject_chairperson(chairperson_id):
    """Reject a pending Chairperson and record the reason."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_PENDING:
        return jsonify({
            "error": "Only pending Chairperson accounts can be rejected"
        }), 409

    reason, error = read_chairperson_rejection_reason()

    if error:
        return error

    chairperson.account_status = User.STATUS_REJECTED
    chairperson.reviewed_by_user_id = session["user_id"]
    chairperson.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    chairperson.rejection_reason = reason

    try:
        invalidate_chairperson_setup_tokens(chairperson.id)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to reject Chairperson account at this time"
        }), 500

    settings = get_primary_settings()
    primary_user_id = (
        settings.primary_chairperson_user_id if settings else None
    )

    return jsonify({
        "message": "Chairperson account rejected",
        "chairperson": serialize_chairperson(
            chairperson,
            primary_user_id
        )
    }), 200


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/deactivate",
    methods=["POST"]
)
def deactivate_chairperson(chairperson_id):
    """Deactivate a Chairperson and clear primary selection if necessary."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_ACTIVE:
        return jsonify({
            "error": "Only active Chairperson accounts can be deactivated"
        }), 409

    settings = get_primary_settings(lock=True)

    if settings is None:
        return jsonify({
            "error": "Chairperson settings are not initialized"
        }), 503

    chairperson.account_status = User.STATUS_DEACTIVATED
    chairperson.reviewed_by_user_id = session["user_id"]
    chairperson.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Do not overwrite rejection_reason during deactivation.
    if settings.primary_chairperson_user_id == chairperson.id:
        settings.primary_chairperson_user_id = None
        settings.updated_by_user_id = session["user_id"]

    try:
        invalidate_chairperson_setup_tokens(chairperson.id)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to deactivate Chairperson at this time"
        }), 500

    return jsonify({
        "message": (
            "Chairperson deactivated. If this account was primary, "
            "the primary selection has been cleared."
        ),
        "chairperson": serialize_chairperson(
            chairperson,
            settings.primary_chairperson_user_id
        )
    }), 200


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/reactivate",
    methods=["POST"]
)
def reactivate_chairperson(chairperson_id):
    """Reactivate a previously deactivated Chairperson."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_DEACTIVATED:
        return jsonify({
            "error": "Only deactivated Chairperson accounts can be reactivated"
        }), 409

    chairperson.account_status = User.STATUS_ACTIVE
    chairperson.reviewed_by_user_id = session["user_id"]
    chairperson.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to reactivate Chairperson at this time"
        }), 500

    settings = get_primary_settings()
    primary_user_id = (
        settings.primary_chairperson_user_id if settings else None
    )

    return jsonify({
        "message": (
            "Chairperson account reactivated. Select it as primary "
            "separately if required."
        ),
        "chairperson": serialize_chairperson(
            chairperson,
            primary_user_id
        )
    }), 200


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/setup-email",
    methods=["POST"]
)
def resend_chairperson_setup_email(chairperson_id):
    """Generate and send a fresh setup link to an active Chairperson."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_ACTIVE:
        return jsonify({
            "error": "Setup email can only be sent to active Chairpersons"
        }), 409

    raw_token, expiry_minutes = create_chairperson_setup_token(chairperson)

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to prepare Chairperson setup email"
        }), 500

    email_sent = send_chairperson_setup_link(
        chairperson,
        raw_token,
        expiry_minutes
    )

    if not email_sent:
        return jsonify({
            "message": "Setup email could not be sent. Check email configuration.",
            "email_sent": False
        }), 202

    return jsonify({
        "message": "Chairperson setup email sent successfully",
        "email_sent": True
    }), 200


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/primary",
    methods=["POST"]
)
def set_primary_chairperson(chairperson_id):
    """Set one active Chairperson as the institution's primary Chairperson."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if not chairperson:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_ACTIVE:
        return jsonify({
            "error": "Only active Chairpersons can be selected as primary"
        }), 409

    settings = get_primary_settings(lock=True)

    if settings is None:
        return jsonify({
            "error": "Chairperson settings are not initialized"
        }), 503

    settings.primary_chairperson_user_id = chairperson.id
    settings.updated_by_user_id = session["user_id"]

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update the primary Chairperson selection"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to set the primary Chairperson at this time"
        }), 500

    return jsonify({
        "message": "Primary Chairperson updated successfully",
        "primary_chairperson_user_id": chairperson.id,
        "chairperson": serialize_chairperson(
            chairperson,
            chairperson.id
        )
    }), 200


def get_user_reference_counts(user_id):
    """
    Find direct foreign-key references to this user across database tables.
    Any existing reference blocks permanent account deletion.
    """
    inspector = inspect(db.engine)
    metadata = MetaData()
    table_cache = {}
    references = []
    checked_columns = set()

    for table_name in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table_name):
            if foreign_key.get("referred_table") != User.__tablename__:
                continue

            local_columns = foreign_key.get("constrained_columns") or []
            remote_columns = foreign_key.get("referred_columns") or []

            for local_column, remote_column in zip(
                local_columns,
                remote_columns
            ):
                if remote_column != "id":
                    continue

                key = (table_name, local_column)

                if key in checked_columns:
                    continue

                checked_columns.add(key)

                if table_name not in table_cache:
                    table_cache[table_name] = Table(
                        table_name,
                        metadata,
                        autoload_with=db.engine
                    )

                table = table_cache[table_name]

                count = db.session.execute(
                    select(func.count())
                    .select_from(table)
                    .where(table.c[local_column] == user_id)
                ).scalar_one()

                if count:
                    references.append({
                        "table": table_name,
                        "column": local_column,
                        "count": int(count)
                    })

    return references


@chairperson_admin_bp.route(
    "/chairpersons/<int:chairperson_id>/delete",
    methods=["POST"]
)
def delete_chairperson(chairperson_id):
    """Permanently delete a deactivated Chairperson with no linked records."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    chairperson = get_chairperson_account(chairperson_id)

    if chairperson is None:
        return jsonify({
            "error": "Chairperson account not found"
        }), 404

    if chairperson.account_status != User.STATUS_DEACTIVATED:
        return jsonify({
            "error": "Only deactivated Chairperson accounts can be deleted. "
                     "Deactivate the account first."
        }), 409

    try:
        references = get_user_reference_counts(chairperson_id)

        if references:
            return jsonify({
                "error": (
                    "This account cannot be permanently deleted because "
                    "other records reference it. The account will remain "
                    "deactivated."
                ),
                "references": references
            }), 409

        db.session.delete(chairperson)
        db.session.commit()

        return jsonify({
            "message": "Chairperson account permanently deleted.",
            "deleted_id": chairperson_id
        }), 200

    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning(
            "Chairperson deletion blocked by a database constraint: %s",
            chairperson_id
        )

        return jsonify({
            "error": (
                "Deletion was blocked because a database record references "
                "this account. The account has not been deleted."
            )
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(
            "Chairperson deletion failed: %s",
            chairperson_id
        )

        return jsonify({
            "error": "A database error prevented account deletion."
        }), 500
