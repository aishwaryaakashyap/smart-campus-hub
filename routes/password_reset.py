import hashlib
import re
import secrets

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import (
    Blueprint, current_app, jsonify, make_response, render_template,
    request, session, url_for
)

from extensions import db
from models import User, PasswordResetToken
from services.email_service import send_password_reset_email


password_reset_bp = Blueprint("password_reset", __name__)

GENERIC_MESSAGE = (
    "If an account with that email exists, "
    "password reset instructions will be sent."
)

INVALID_TOKEN_MESSAGE = (
    "This reset link is invalid or has expired. "
    "Please request a new one."
)


@password_reset_bp.route("/forgot-password-page", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")


@password_reset_bp.route("/reset-password-page", methods=["GET"])
def reset_password_page():
    response = make_response(render_template(
        "reset_password.html",
        token=""
    ))
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@password_reset_bp.route("/forgot-password", methods=["POST"])
def request_password_reset():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON object is required"}), 400

    email_value = data.get("email")

    if not isinstance(email_value, str):
        return jsonify({"error": "A valid email address is required"}), 400

    email = email_value.strip().lower()

    if (
        not email
        or len(email) > 120
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
    ):
        return jsonify({"error": "A valid email address is required"}), 400

    base_url = current_app.config.get("APP_BASE_URL", "")
    parsed_url = urlsplit(base_url)

    email_configured = all((
        current_app.config.get("MAIL_SERVER"),
        current_app.config.get("MAIL_DEFAULT_SENDER"),
        parsed_url.scheme in ("http", "https"),
        bool(parsed_url.netloc),
    ))

    if not email_configured:
        current_app.logger.warning(
            "Password reset email configuration is incomplete."
        )
        return jsonify({"message": GENERIC_MESSAGE}), 200

    user = User.query.filter_by(email=email).first()

    if user is None:
        return jsonify({"message": GENERIC_MESSAGE}), 200

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    recent_request = PasswordResetToken.query.filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.created_at >= now - timedelta(seconds=60)
    ).first()

    if recent_request:
        return jsonify({"message": GENERIC_MESSAGE}), 200

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    expiry_minutes = current_app.config.get(
        "PASSWORD_RESET_TOKEN_MINUTES", 15
    )

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(minutes=expiry_minutes)
    )

    try:
        db.session.add(reset_record)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not create password reset record."
        )
        return jsonify({"message": GENERIC_MESSAGE}), 200

    reset_path = url_for("password_reset.reset_password_page")
    reset_url = f"{base_url}{reset_path}#token={raw_token}"

    try:
        send_password_reset_email(user.email, reset_url)

        # Invalidate older outstanding links only after email succeeds.
        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_record.id,
            PasswordResetToken.used_at.is_(None)
        ).delete(synchronize_session=False)

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Password reset email delivery failed."
        )

        try:
            PasswordResetToken.query.filter_by(
                token_hash=token_hash
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({"message": GENERIC_MESSAGE}), 200


@password_reset_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A valid JSON object is required"}), 400

    token = data.get("token")
    password = data.get("password")
    confirm_password = data.get("confirm_password")

    if (
        not isinstance(token, str)
        or not token
        or len(token) > 200
        or not isinstance(password, str)
        or not isinstance(confirm_password, str)
    ):
        return jsonify({"error": "Invalid reset request"}), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters long"
        }), 400

    if len(password) > 128:
        return jsonify({
            "error": "Password must be 128 characters or fewer"
        }), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    reset_record = PasswordResetToken.query.filter_by(
        token_hash=token_hash
    ).first()

    if (
        reset_record is None
        or reset_record.used_at is not None
        or reset_record.expires_at <= now
    ):
        return jsonify({"error": INVALID_TOKEN_MESSAGE}), 400

    user = db.session.get(User, reset_record.user_id)

    if user is None:
        return jsonify({"error": INVALID_TOKEN_MESSAGE}), 400

    try:
        # Atomically claim the token so it cannot be used twice.
        claimed = PasswordResetToken.query.filter(
            PasswordResetToken.id == reset_record.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now
        ).update(
            {"used_at": now},
            synchronize_session=False
        )

        if claimed != 1:
            db.session.rollback()
            return jsonify({"error": INVALID_TOKEN_MESSAGE}), 400

        user.set_password(password)

        # Invalidate any other outstanding tokens for this account.
        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_record.id,
            PasswordResetToken.used_at.is_(None)
        ).delete(synchronize_session=False)

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Password reset could not be completed."
        )
        return jsonify({
            "error": "Unable to reset password. Please try again."
        }), 500

    session.clear()

    return jsonify({
        "message": "Password reset successfully. Please log in again."
    }), 200
