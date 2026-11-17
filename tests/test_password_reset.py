import hashlib
import unittest
from pathlib import Path

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from extensions import db
from models import User, PasswordResetToken
from routes.auth import auth_bp
from routes.password_reset import password_reset_bp


class PasswordResetTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        project_templates = (
            Path(__file__).resolve().parents[1] / "templates"
        )
        cls.app = Flask(
            __name__,
            template_folder=str(project_templates)
        )
        cls.app.config.update(
            TESTING=True,
            SECRET_KEY="isolated-password-reset-test-key",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            WTF_CSRF_ENABLED=False,
            MAIL_SERVER="smtp.test.local",
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            MAIL_DEFAULT_SENDER="noreply@test.local",
            MAIL_USERNAME="test-user",
            MAIL_PASSWORD="test-password",
            APP_BASE_URL="https://test.smartcampus.example",
            PASSWORD_RESET_TOKEN_MINUTES=15,
        )

        db.init_app(cls.app)
        CSRFProtect(cls.app)
        cls.app.register_blueprint(auth_bp, url_prefix="/api/auth")
        cls.app.register_blueprint(
            password_reset_bp,
            url_prefix="/api/auth"
        )

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()

        db.metadata.create_all(bind=db.engine, tables=[
            User.__table__,
            PasswordResetToken.__table__,
        ])

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.metadata.drop_all(bind=db.engine, tables=[
            PasswordResetToken.__table__,
            User.__table__,
        ])
        self.context.pop()

    def create_user(self, role, email):
        user = User(
            name="Password Reset Test",
            email=email,
            role=role,
        )
        user.set_password("OldPassword123")
        db.session.add(user)
        db.session.commit()
        return user

    def request_reset(self, email):
        return self.client.post(
            "/api/auth/forgot-password",
            json={"email": email},
        )

    def extract_token(self, mocked_email):
        reset_url = mocked_email.call_args.args[1]
        parsed_url = urlparse(reset_url)
        self.assertEqual(parsed_url.query, "")
        fragment = parse_qs(parsed_url.fragment)
        return fragment["token"][0]

    def test_all_three_roles_can_reset_password(self):
        roles = ["student", "coordinator", "advisor"]

        with patch(
            "routes.password_reset.send_password_reset_email"
        ) as mocked_email:

            for role in roles:
                with self.subTest(role=role):
                    email = f"{role}@example.test"
                    user = self.create_user(role, email)

                    response = self.request_reset(email)

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        response.get_json()["message"],
                        "If an account with that email exists, "
                        "password reset instructions will be sent."
                    )
                    self.assertTrue(mocked_email.called)

                    token = self.extract_token(mocked_email)

                    token_hash = hashlib.sha256(
                        token.encode("utf-8")
                    ).hexdigest()

                    record = PasswordResetToken.query.filter_by(
                        token_hash=token_hash
                    ).first()

                    self.assertIsNotNone(record)
                    self.assertNotEqual(record.token_hash, token)
                    self.assertEqual(record.user_id, user.id)

                    reset_response = self.client.post(
                        "/api/auth/reset-password",
                        json={
                            "token": token,
                            "password": "NewPassword456",
                            "confirm_password": "NewPassword456",
                        },
                    )

                    self.assertEqual(reset_response.status_code, 200)

                    db.session.refresh(user)
                    self.assertTrue(
                        user.check_password("NewPassword456")
                    )

                    # Verify the existing login endpoint accepts the
                    # new password for each supported user role.
                    login_response = self.client.post(
                        "/api/auth/login",
                        json={
                            "email": email,
                            "password": "NewPassword456",
                        },
                    )

                    self.assertEqual(login_response.status_code, 200)
                    self.assertEqual(
                        login_response.get_json()["role"], role
                    )

                    db.session.refresh(record)
                    self.assertIsNotNone(record.used_at)

                    # The same token must not work twice.
                    repeated_response = self.client.post(
                        "/api/auth/reset-password",
                        json={
                            "token": token,
                            "password": "AnotherPassword789",
                            "confirm_password": "AnotherPassword789",
                        },
                    )

                    self.assertEqual(
                        repeated_response.status_code, 400
                    )

                    db.session.refresh(user)
                    self.assertTrue(
                        user.check_password("NewPassword456")
                    )

    def test_unknown_email_gets_same_generic_response(self):
        self.create_user("student", "known@example.test")

        with patch(
            "routes.password_reset.send_password_reset_email"
        ) as mocked_email:
            known = self.request_reset("known@example.test")
            unknown = self.request_reset("unknown@example.test")

        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.get_json(), unknown.get_json())
        mocked_email.assert_called_once()

    def test_recent_reset_request_is_rate_limited(self):
        self.create_user("student", "rate@example.test")

        with patch(
            "routes.password_reset.send_password_reset_email"
        ) as mocked_email:

            first = self.request_reset("rate@example.test")
            second = self.request_reset("rate@example.test")

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            mocked_email.assert_called_once()

    def test_reset_page_has_no_store_and_referrer_security_headers(self):
        response = self.client.get("/api/auth/reset-password-page")

        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertEqual(
            response.headers.get("Referrer-Policy"), "no-referrer"
        )
        self.assertEqual(
            response.headers.get("X-Content-Type-Options"), "nosniff"
        )
        self.assertNotIn(b"test-reset-token", response.data)

    def test_expired_token_is_rejected(self):
        user = self.create_user("student", "expired@example.test")

        token = "expired-test-token"
        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        db.session.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        ))
        db.session.commit()

        response = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "password": "NewPassword456",
                "confirm_password": "NewPassword456",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(user.check_password("OldPassword123"))

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": "some-token",
                "password": "NewPassword456",
                "confirm_password": "DifferentPassword789",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "Passwords do not match",
        )

    def test_short_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/reset-password",
            json={
                "token": "some-token",
                "password": "short",
                "confirm_password": "short",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_forgot_password_rejects_missing_csrf_token(self):
        self.app.config["WTF_CSRF_ENABLED"] = True

        try:
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "student@example.test"},
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn(b"CSRF", response.data)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    def test_missing_csrf_token_is_rejected(self):
        self.app.config["WTF_CSRF_ENABLED"] = True

        try:
            response = self.client.post(
                "/api/auth/reset-password",
                json={
                    "token": "some-token",
                    "password": "NewPassword456",
                    "confirm_password": "NewPassword456",
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn(b"CSRF", response.data)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False


if __name__ == "__main__":
    unittest.main()
