import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app import app


class AcademicClassArchiveTests(unittest.TestCase):

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

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = user_id
            current_session["role"] = role

    def coordinator(self):
        return SimpleNamespace(
            id=1,
            role="coordinator",
            account_status="active"
        )

    def academic_class(self, is_active=True):
        advisor = SimpleNamespace(
            id=25,
            name="Test Advisor",
            email="advisor@example.com",
            account_status="active"
        )

        return SimpleNamespace(
            id=10,
            course="BCA",
            branch="CSE",
            section="A",
            admission_year=2024,
            advisor_user_id=25,
            advisor=advisor,
            is_active=is_active,
            created_at=None,
            updated_at=None
        )

    def test_unauthenticated_user_cannot_archive_class(self):
        response = self.client.patch(
            "/api/academic-admin/classes/10/archive"
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_archive_class(self):
        self.set_session(role="student")

        student = SimpleNamespace(
            role="student",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=student
        ):
            response = self.client.patch(
                "/api/academic-admin/classes/10/archive"
            )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_restore_class(self):
        response = self.client.patch(
            "/api/academic-admin/classes/10/restore"
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_restore_class(self):
        self.set_session(role="student")

        student = SimpleNamespace(
            role="student",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=student
        ):
            response = self.client.patch(
                "/api/academic-admin/classes/10/restore"
            )

        self.assertEqual(response.status_code, 403)

    def test_archive_nonexistent_class_returns_404(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=None
        ):
            response = self.client.patch(
                "/api/academic-admin/classes/999/archive"
            )

        self.assertEqual(response.status_code, 404)

    def test_restore_nonexistent_class_returns_404(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=None
        ):
            response = self.client.patch(
                "/api/academic-admin/classes/999/restore"
            )

        self.assertEqual(response.status_code, 404)

    def test_coordinator_can_archive_class(self):
        self.set_session()
        academic_class = self.academic_class(is_active=True)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            response = self.client.patch(
                "/api/academic-admin/classes/10/archive"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Academic class archived successfully"
        )
        self.assertFalse(academic_class.is_active)

        # The Advisor relationship remains unchanged.
        self.assertEqual(academic_class.advisor_user_id, 25)
        self.assertIsNotNone(academic_class.advisor)

        self.assertFalse(response.get_json()["class"]["is_active"])
        commit.assert_called_once()

    def test_coordinator_can_restore_class(self):
        self.set_session()
        academic_class = self.academic_class(is_active=False)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            response = self.client.patch(
                "/api/academic-admin/classes/10/restore"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Academic class restored successfully"
        )
        self.assertTrue(academic_class.is_active)

        self.assertEqual(academic_class.advisor_user_id, 25)
        self.assertIsNotNone(academic_class.advisor)

        self.assertTrue(response.get_json()["class"]["is_active"])
        commit.assert_called_once()

    def test_archiving_already_archived_class_is_safe(self):
        self.set_session()
        academic_class = self.academic_class(is_active=False)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            response = self.client.patch(
                "/api/academic-admin/classes/10/archive"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("already archived", response.get_json()["message"])
        commit.assert_not_called()

    def test_restoring_already_active_class_is_safe(self):
        self.set_session()
        academic_class = self.academic_class(is_active=True)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            response = self.client.patch(
                "/api/academic-admin/classes/10/restore"
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("already active", response.get_json()["message"])
        commit.assert_not_called()

    def test_archive_database_error_rolls_back(self):
        self.set_session()
        academic_class = self.academic_class(is_active=True)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit",
            side_effect=SQLAlchemyError("Database error")
        ), patch(
            "routes.academic_admin.db.session.rollback"
        ) as rollback:

            response = self.client.patch(
                "/api/academic-admin/classes/10/archive"
            )

        self.assertEqual(response.status_code, 500)
        rollback.assert_called_once()

    def test_restore_database_error_rolls_back(self):
        self.set_session()
        academic_class = self.academic_class(is_active=False)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.db.session.commit",
            side_effect=SQLAlchemyError("Database error")
        ), patch(
            "routes.academic_admin.db.session.rollback"
        ) as rollback:

            response = self.client.patch(
                "/api/academic-admin/classes/10/restore"
            )

        self.assertEqual(response.status_code, 500)
        rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
