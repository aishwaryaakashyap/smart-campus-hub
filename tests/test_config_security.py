import unittest

from app import app


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
        # Flask defaults this setting to True unless overridden.
        self.assertTrue(
            app.config.get("SESSION_COOKIE_HTTPONLY", True)
        )


if __name__ == "__main__":
    unittest.main()
