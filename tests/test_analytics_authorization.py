import unittest

from app import app


class AnalyticsAuthorizationTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        app.config["TESTING"] = True
        self.client = app.test_client()

        self.endpoints = [
            "/api/analytics/placement",
            "/api/analytics/dashboard",
            "/api/analytics/advanced",
        ]

    def tearDown(self):
        app.config["TESTING"] = self.previous_testing

    def test_all_analytics_endpoints_reject_unauthenticated_users(self):
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)

                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.get_json()["error"],
                    "Not logged in"
                )

    def test_all_analytics_endpoints_reject_students(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "student"

        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)

                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.get_json()["error"],
                    "Only coordinators can view placement analytics"
                )


if __name__ == "__main__":
    unittest.main()
