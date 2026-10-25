import unittest
from unittest.mock import MagicMock, patch

from app import app


class CoordinatorGrievanceUITests(unittest.TestCase):

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

    def test_coordinator_page_redirects_unauthenticated_user(self):
        response = self.client.get("/coordinator/grievances")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/api/auth/login-page", response.location)

    def test_coordinator_page_rejects_student(self):
        self.set_session(user_id=1, role="student")

        response = self.client.get("/coordinator/grievances")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can access grievance management",
        )

    def test_coordinator_page_renders_for_coordinator(self):
        self.set_session(user_id=22, role="coordinator")

        coordinator = MagicMock()
        coordinator.id = 22
        coordinator.name = "Test Coordinator"
        coordinator.role = "coordinator"

        with patch(
            "app.db.session.get",
            return_value=coordinator,
        ):
            response = self.client.get("/coordinator/grievances")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Grievance Management", response.data)
        self.assertIn(b"Assign advisor", response.data)
        self.assertIn(b"Update status", response.data)

    def test_coordinator_page_rejects_missing_coordinator_record(self):
        self.set_session(user_id=999999, role="coordinator")

        with patch("app.db.session.get", return_value=None):
            response = self.client.get("/coordinator/grievances")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/api/auth/login-page", response.location)

    def test_advisor_list_requires_login(self):
        response = self.client.get("/api/grievances/advisors")

        self.assertEqual(response.status_code, 401)

    def test_advisor_list_rejects_student(self):
        self.set_session(user_id=1, role="student")

        response = self.client.get("/api/grievances/advisors")

        self.assertEqual(response.status_code, 403)

    def test_advisor_list_returns_advisors_to_coordinator(self):
        self.set_session(user_id=22, role="coordinator")

        advisor = MagicMock()
        advisor.id = 33
        advisor.name = "Test Advisor"
        advisor.email = "advisor@example.test"

        with patch(
            "routes.grievance.User.query"
        ) as user_query:
            user_query.filter_by.return_value.order_by.return_value.all.return_value = [
                advisor
            ]

            response = self.client.get("/api/grievances/advisors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [{
                "id": 33,
                "name": "Test Advisor",
                "email": "advisor@example.test",
            }],
        )

    def test_staff_history_requires_login(self):
        response = self.client.get(
            "/api/grievances/manage/10/history"
        )

        self.assertEqual(response.status_code, 401)

    def test_staff_history_rejects_student(self):
        self.set_session(user_id=1, role="student")

        response = self.client.get(
            "/api/grievances/manage/10/history"
        )

        self.assertEqual(response.status_code, 403)

    def test_coordinator_can_view_grievance_history(self):
        self.set_session(user_id=22, role="coordinator")

        grievance = MagicMock()
        grievance.id = 10

        update = MagicMock()
        update.old_status = "Submitted"
        update.new_status = "Under Review"
        update.comment = "Review started"
        update.created_at.isoformat.return_value = "2026-10-25T10:00:00"
        update.updated_by = 22

        with patch(
            "routes.grievance.db.session.get",
            return_value=grievance,
        ), patch(
            "routes.grievance.GrievanceUpdate.query"
        ) as update_query:
            update_query.filter_by.return_value.order_by.return_value.all.return_value = [
                update
            ]

            response = self.client.get(
                "/api/grievances/manage/10/history"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()[0]["new_status"], "Under Review")
        self.assertEqual(response.get_json()[0]["comment"], "Review started")

    def test_advisor_cannot_view_unassigned_grievance_history(self):
        self.set_session(user_id=33, role="advisor")

        grievance = MagicMock()
        grievance.id = 10
        grievance.assigned_to = 44

        with patch(
            "routes.grievance.db.session.get",
            return_value=grievance,
        ):
            response = self.client.get(
                "/api/grievances/manage/10/history"
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "You can view only grievances assigned to you",
        )


if __name__ == "__main__":
    unittest.main()
