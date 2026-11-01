import unittest
from unittest.mock import patch

from app import app


class PlacementDriveRouteTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)
        self.client = app.test_client()

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_rejects_unauthenticated_create(self):
        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "Python Developer"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_rejects_student_creating_drive(self):
        self.set_session(role="student")
        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "Python Developer"},
        )
        self.assertEqual(response.status_code, 403)

    def test_rejects_missing_company_id(self):
        self.set_session()
        response = self.client.post(
            "/api/drives/",
            json={"job_role": "Python Developer"},
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_blank_job_role(self):
        self.set_session()
        response = self.client.post(
            "/api/drives/",
            json={"company_id": 1, "job_role": "   "},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "job_role must be a non-empty string",
        )

    @patch("routes.placement_drive.Company.query")
    def test_returns_404_when_company_does_not_exist(self, company_query):
        self.set_session()
        company_query.get.return_value = None
        response = self.client.post(
            "/api/drives/",
            json={"company_id": 999, "job_role": "Python Developer"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Company not found")


if __name__ == "__main__":
    unittest.main()
