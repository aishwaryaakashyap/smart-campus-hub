import unittest

from app import app
from config import validate_production_config


class SessionCookieSecurityTests(unittest.TestCase):

    def test_session_cookie_samesite_is_lax(self):
        self.assertEqual(
            app.config.get("SESSION_COOKIE_SAMESITE"),
            "Lax"
        )

    def test_session_cookie_secure_setting_is_boolean(self):
        self.assertIsInstance(
            app.config.get("SESSION_COOKIE_SECURE"),
            bool
        )

    def test_session_cookie_http_only_is_enabled(self):
        self.assertTrue(
            app.config.get("SESSION_COOKIE_HTTPONLY", True)
        )


class ProductionConfigurationValidationTests(unittest.TestCase):

    def valid_config(self):
        return {
            "SECRET_KEY": "A" * 40,
            "SQLALCHEMY_DATABASE_URI": (
                "mysql+pymysql://campus_app:secure_password"
                "@db.example.com/smart_campus_hub"
            ),
            "APP_BASE_URL": "https://campus.example.com",
            "SESSION_COOKIE_SECURE": True,
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "WTF_CSRF_ENABLED": True,
            "MAIL_SERVER": "smtp.gmail.com",
            "MAIL_PORT": 587,
            "MAIL_USE_TLS": True,
            "MAIL_USERNAME": "campus@example.com",
            "MAIL_PASSWORD": "example-app-password",
            "MAIL_DEFAULT_SENDER": "campus@example.com",
        }

    def test_valid_production_configuration_passes(self):
        self.assertTrue(
            validate_production_config(self.valid_config())
        )

    def test_weak_secret_key_is_rejected(self):
        config = self.valid_config()
        config["SECRET_KEY"] = "short"

        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            validate_production_config(config)

    def test_sqlite_database_is_rejected(self):
        config = self.valid_config()
        config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///production.db"

        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            validate_production_config(config)

    def test_non_https_application_url_is_rejected(self):
        config = self.valid_config()
        config["APP_BASE_URL"] = "http://campus.example.com"

        with self.assertRaisesRegex(RuntimeError, "APP_BASE_URL"):
            validate_production_config(config)

    def test_local_application_url_is_rejected(self):
        config = self.valid_config()
        config["APP_BASE_URL"] = "https://localhost"

        with self.assertRaisesRegex(RuntimeError, "APP_BASE_URL"):
            validate_production_config(config)

    def test_insecure_session_cookie_is_rejected(self):
        config = self.valid_config()
        config["SESSION_COOKIE_SECURE"] = False

        with self.assertRaisesRegex(
            RuntimeError,
            "SESSION_COOKIE_SECURE"
        ):
            validate_production_config(config)

    def test_disabled_csrf_is_rejected(self):
        config = self.valid_config()
        config["WTF_CSRF_ENABLED"] = False

        with self.assertRaisesRegex(RuntimeError, "WTF_CSRF_ENABLED"):
            validate_production_config(config)

    def test_smtp_without_tls_is_rejected(self):
        config = self.valid_config()
        config["MAIL_USE_TLS"] = False

        with self.assertRaisesRegex(RuntimeError, "MAIL_USE_TLS"):
            validate_production_config(config)

    def test_missing_smtp_password_is_rejected(self):
        config = self.valid_config()
        config["MAIL_PASSWORD"] = ""

        with self.assertRaisesRegex(RuntimeError, "MAIL_PASSWORD"):
            validate_production_config(config)


if __name__ == "__main__":
    unittest.main()
