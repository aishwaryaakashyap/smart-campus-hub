import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class AcademicClassEditTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        self.app_context = app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.addCleanup(
            app.config.__setitem__,
            "TESTING",
            self.previous_testing
        )
        self.addCleanup(
            app.config.__setitem__,
            "WTF_CSRF_ENABLED",
            self.previous_csrf
        )

        self.client = app.test_client()

    def set_coordinator_session(self):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 1
            current_session["role"] = "coordinator"

    def coordinator(self):
        return SimpleNamespace(
            id=1,
            role="coordinator",
            account_status="active"
        )

    def academic_class(self):
        return SimpleNamespace(
            id=10,
            course="BCA",
            branch="CSE",
            section="A",
            admission_year=2024,
            advisor_user_id=None,
            advisor=None,
            is_active=True,
            created_at=None,
            updated_at=None
        )

    def valid_payload(self):
        return {
            "course": "BCA",
            "branch": "CSE",
            "section": "B",
            "admission_year": 2024
        }

    def test_unauthenticated_user_cannot_edit_class(self):
        response = self.client.put(
            "/api/academic-admin/classes/10",
            json=self.valid_payload()
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_edit_class(self):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 2
            current_session["role"] = "student"

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=SimpleNamespace(
                role="student",
                account_status="active"
            )
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 403)

    def test_missing_class_returns_404(self):
        self.set_coordinator_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=None
        ):
            response = self.client.put(
                "/api/academic-admin/classes/999",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 404)

    def test_invalid_json_is_rejected(self):
        self.set_coordinator_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=self.academic_class()
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10",
                json=["BCA", "CSE"]
            )

        self.assertEqual(response.status_code, 400)

    def test_missing_field_is_rejected(self):
        self.set_coordinator_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=self.academic_class()
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10",
                json={"course": "BCA"}
            )

        self.assertEqual(response.status_code, 400)

    def test_assigned_students_prevent_identity_change(self):
        self.set_coordinator_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=self.academic_class()
        ), patch(
            "routes.academic_admin.Student.query"
        ) as student_query, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.count.return_value = 2

            response = self.client.put(
                "/api/academic-admin/classes/10",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 409)
        commit.assert_not_called()

    def test_duplicate_class_identity_is_rejected(self):
        self.set_coordinator_session()

        existing = SimpleNamespace(id=20)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=self.academic_class()
        ), patch(
            "routes.academic_admin.Student.query"
        ) as student_query, patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query:

            student_query.filter_by.return_value.count.return_value = 0
            class_query.filter.return_value.first.return_value = existing

            response = self.client.put(
                "/api/academic-admin/classes/10",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 409)

    def test_successfully_updates_class_without_assigned_students(self):
        self.set_coordinator_session()

        class_record = self.academic_class()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=class_record
        ), patch(
            "routes.academic_admin.Student.query"
        ) as student_query, patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.count.return_value = 0
            class_query.filter.return_value.first.return_value = None

            response = self.client.put(
                "/api/academic-admin/classes/10",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["class"]["section"],
            "B"
        )
        self.assertEqual(class_record.section, "B")
        commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
