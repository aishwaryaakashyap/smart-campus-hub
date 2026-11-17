import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import session

from app import app


class StudentProfileSecurityTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.addCleanup(
            app.config.__setitem__, "TESTING", self.previous_testing
        )
        self.addCleanup(
            app.config.__setitem__, "WTF_CSRF_ENABLED", self.previous_csrf
        )

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        self.client = app.test_client()

        self.current_user_patcher = patch(
            "routes.student.get_session_user",
            side_effect=lambda user_id: SimpleNamespace(
                role=session.get("role")
            )
        )
        self.current_user_patcher.start()
        self.addCleanup(self.current_user_patcher.stop)

    def set_session(self, user_id=10, role="student"):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = user_id
            current_session["role"] = role

    def assert_session_cleared(self):
        with self.client.session_transaction() as current_session:
            self.assertNotIn("user_id", current_session)
            self.assertNotIn("role", current_session)

    def test_unauthenticated_user_cannot_view_profile(self):
        response = self.client.get("/api/students/profile")
        self.assertEqual(response.status_code, 401)

    def test_non_student_cannot_view_student_profile(self):
        self.set_session(user_id=20, role="coordinator")

        response = self.client.get("/api/students/profile")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only students can perform this action"
        )

    def test_stale_student_session_is_cleared_after_role_change(self):
        self.set_session(user_id=30, role="student")

        changed_user = SimpleNamespace(role="coordinator")

        with patch(
            "routes.student.get_session_user",
            return_value=changed_user
        ):
            response = self.client.get("/api/students/profile")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")
        self.assert_session_cleared()

    def test_missing_account_clears_student_session(self):
        self.set_session(user_id=99, role="student")

        with patch(
            "routes.student.get_session_user",
            return_value=None
        ):
            response = self.client.get("/api/students/profile")

        self.assertEqual(response.status_code, 401)
        self.assert_session_cleared()

    def test_student_without_profile_receives_404(self):
        self.set_session()

        with patch(
            "routes.student.Student.query"
        ) as student_query:
            student_query.filter_by.return_value.first.return_value = None

            response = self.client.get("/api/students/profile")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Profile not found")

    def test_student_can_view_own_profile(self):
        self.set_session(user_id=10, role="student")

        student = SimpleNamespace(
            id=5,
            register_number="TEST123",
            course="BCA",
            branch="Computer Science",
            semester=5,
            cgpa=7.5,
            phone="9999999999",
            graduation_year=2028
        )

        with patch(
            "routes.student.Student.query"
        ) as student_query:
            student_query.filter_by.return_value.first.return_value = student

            response = self.client.get("/api/students/profile")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], 5)
        self.assertEqual(
            response.get_json()["register_number"],
            "TEST123"
        )

    def test_stale_role_cannot_create_profile(self):
        self.set_session(user_id=30, role="student")

        changed_user = SimpleNamespace(role="coordinator")

        with patch(
            "routes.student.get_session_user",
            return_value=changed_user
        ), patch(
            "routes.student.Student.query"
        ) as student_query:

            response = self.client.post(
                "/api/students/profile",
                json={"register_number": "TEST123"}
            )

        self.assertEqual(response.status_code, 401)
        student_query.filter_by.assert_not_called()
        self.assert_session_cleared()

    def test_stale_role_cannot_update_profile(self):
        self.set_session(user_id=30, role="student")

        changed_user = SimpleNamespace(role="coordinator")

        with patch(
            "routes.student.get_session_user",
            return_value=changed_user
        ), patch(
            "routes.student.Student.query"
        ) as student_query:

            response = self.client.put(
                "/api/students/profile",
                json={"semester": 6}
            )

        self.assertEqual(response.status_code, 401)
        student_query.filter_by.assert_not_called()
        self.assert_session_cleared()


if __name__ == "__main__":
    unittest.main()
