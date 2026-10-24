
import unittest

from app import app


class AnalyticsAuthorizationTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def set_session(self, user_id=1, role="student"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_placement_analytics_rejects_unauthenticated_user(self):
        response = self.client.get("/api/analytics/placement")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_placement_analytics_rejects_student(self):
        self.set_session(role="student")
        response = self.client.get("/api/analytics/placement")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can view placement analytics",
        )

    def test_analytics_dashboard_rejects_unauthenticated_user(self):
        response = self.client.get("/api/analytics/dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_analytics_dashboard_rejects_student(self):
        self.set_session(role="student")
        response = self.client.get("/api/analytics/dashboard")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can view placement analytics",
        )

    def test_advanced_analytics_rejects_unauthenticated_user(self):
        response = self.client.get("/api/analytics/advanced")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_advanced_analytics_rejects_student(self):
        self.set_session(role="student")
        response = self.client.get("/api/analytics/advanced")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can view placement analytics",
        )


if __name__ == "__main__":
    unittest.main()
