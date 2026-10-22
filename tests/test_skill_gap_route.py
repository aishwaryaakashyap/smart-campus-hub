import unittest

from app import app


class SkillGapRouteSecurityTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def tearDown(self):
        app.config["TESTING"] = self.previous_testing
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf

    def test_rejects_unauthenticated_user(self):
        response = self.client.get("/api/skill-gap/1")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_rejects_non_student_user(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 2
            session["role"] = "coordinator"

        response = self.client.get("/api/skill-gap/1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only students can view their skill gap"
        )


if __name__ == "__main__":
    unittest.main()
