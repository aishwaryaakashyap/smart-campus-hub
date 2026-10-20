import re
import unittest

from app import app


class CSRFProtectionTests(unittest.TestCase):

    def setUp(self):
        self.previous_csrf_setting = app.config.get(
            "WTF_CSRF_ENABLED", True
        )
        app.config["WTF_CSRF_ENABLED"] = True
        self.client = app.test_client()

    def tearDown(self):
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf_setting

    def test_login_rejects_request_without_csrf_token(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPass123"
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"CSRF token is missing", response.data)

    def test_login_page_contains_csrf_token(self):
        response = self.client.get("/api/auth/login-page")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="csrf-token"', response.data)

        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            response.data
        )

        self.assertIsNotNone(match)
        self.assertTrue(match.group(1))

    def test_login_accepts_valid_csrf_token(self):
        page_response = self.client.get("/api/auth/login-page")

        self.assertEqual(page_response.status_code, 200)

        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            page_response.data
        )

        self.assertIsNotNone(match)
        csrf_token = match.group(1).decode("utf-8")

        response = self.client.post(
            "/api/auth/login",
            json={},
            headers={"X-CSRFToken": csrf_token}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Email and password are required", response.data)

    def test_notification_update_rejects_request_without_csrf_token(self):
        response = self.client.put("/api/notifications/1/read")

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"CSRF token is missing", response.data)


if __name__ == "__main__":
    unittest.main()