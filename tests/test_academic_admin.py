import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from app import app


class AcademicAdminAuthorizationTests(unittest.TestCase):

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

    def assert_session_cleared(self):
        with self.client.session_transaction() as current_session:
            self.assertNotIn("user_id", current_session)
            self.assertNotIn("role", current_session)

    def active_coordinator(self):
        return SimpleNamespace(
            id=1,
            role="coordinator",
            account_status="active"
        )

    def test_unauthenticated_user_cannot_list_classes(self):
        response = self.client.get(
            "/api/academic-admin/classes"
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_list_classes(self):
        self.set_session(role="student")

        student_user = SimpleNamespace(
            role="student",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=student_user
        ):
            response = self.client.get(
                "/api/academic-admin/classes"
            )

        self.assertEqual(response.status_code, 403)

    def test_inactive_coordinator_cannot_list_classes(self):
        self.set_session(role="coordinator")

        inactive_user = SimpleNamespace(
            role="coordinator",
            account_status="deactivated"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=inactive_user
        ):
            response = self.client.get(
                "/api/academic-admin/classes"
            )

        self.assertEqual(response.status_code, 401)
        self.assert_session_cleared()

    def test_stale_coordinator_session_is_rejected(self):
        self.set_session(role="coordinator")

        changed_user = SimpleNamespace(
            role="advisor",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=changed_user
        ):
            response = self.client.get(
                "/api/academic-admin/classes"
            )

        self.assertEqual(response.status_code, 401)
        self.assert_session_cleared()

    def test_active_coordinator_can_list_classes(self):
        self.set_session(role="coordinator")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ), patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query:

            class_query.filter_by.return_value.order_by.return_value.all.return_value = []

            response = self.client.get(
                "/api/academic-admin/classes"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "classes": [],
            "total": 0
        })

    def test_invalid_include_archived_value_is_rejected(self):
        self.set_session(role="coordinator")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ):
            response = self.client.get(
                "/api/academic-admin/classes?include_archived=yes"
            )

        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_user_cannot_create_class(self):
        response = self.client.post(
            "/api/academic-admin/classes",
            json={
                "course": "BCA",
                "branch": "CSE",
                "section": "A",
                "admission_year": 2024
            }
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_create_class(self):
        self.set_session(role="student")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=SimpleNamespace(
                role="student",
                account_status="active"
            )
        ):
            response = self.client.post(
                "/api/academic-admin/classes",
                json={
                    "course": "BCA",
                    "branch": "CSE",
                    "section": "A",
                    "admission_year": 2024
                }
            )

        self.assertEqual(response.status_code, 403)

    def test_non_object_json_is_rejected(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ):
            response = self.client.post(
                "/api/academic-admin/classes",
                json=["BCA", "CSE"]
            )

        self.assertEqual(response.status_code, 400)

    def test_missing_required_fields_are_rejected(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ):
            response = self.client.post(
                "/api/academic-admin/classes",
                json={"course": "BCA"}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("branch", response.get_json()["error"])

    def test_blank_class_fields_are_rejected(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ):
            response = self.client.post(
                "/api/academic-admin/classes",
                json={
                    "course": "BCA",
                    "branch": "   ",
                    "section": "A",
                    "admission_year": 2024
                }
            )

        self.assertEqual(response.status_code, 400)

    def test_invalid_admission_year_is_rejected(self):
        self.set_session()

        invalid_years = [
            True,
            False,
            "2024",
            1899,
            2101
        ]

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ):
            for year in invalid_years:
                with self.subTest(year=year):
                    response = self.client.post(
                        "/api/academic-admin/classes",
                        json={
                            "course": "BCA",
                            "branch": "CSE",
                            "section": "A",
                            "admission_year": year
                        }
                    )

                    self.assertEqual(response.status_code, 400)

    def test_duplicate_class_is_rejected(self):
        self.set_session()

        existing = SimpleNamespace(id=10)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ), patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query:

            class_query.filter_by.return_value.first.return_value = existing

            response = self.client.post(
                "/api/academic-admin/classes",
                json={
                    "course": "BCA",
                    "branch": "CSE",
                    "section": "A",
                    "admission_year": 2024
                }
            )

        self.assertEqual(response.status_code, 409)

    def test_successfully_creates_academic_class(self):
        self.set_session()

        def assign_id(academic_class):
            academic_class.id = 101

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ), patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query, patch(
            "routes.academic_admin.db.session.add",
            side_effect=assign_id
        ) as add_record, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            class_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                "/api/academic-admin/classes",
                json={
                    "course": " BCA ",
                    "branch": " CSE ",
                    "section": " A ",
                    "admission_year": 2024
                }
            )

        self.assertEqual(response.status_code, 201)

        result = response.get_json()

        self.assertEqual(
            result["message"],
            "Academic class created successfully"
        )
        self.assertEqual(result["class"]["id"], 101)
        self.assertEqual(result["class"]["course"], "BCA")
        self.assertEqual(result["class"]["branch"], "CSE")
        self.assertEqual(result["class"]["section"], "A")
        self.assertEqual(result["class"]["admission_year"], 2024)
        self.assertTrue(result["class"]["is_active"])

        add_record.assert_called_once()
        commit.assert_called_once()

    def test_database_unique_constraint_conflict_returns_409(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.active_coordinator()
        ), patch(
            "routes.academic_admin.AcademicClass.query"
        ) as class_query, patch(
            "routes.academic_admin.db.session.add"
        ), patch(
            "routes.academic_admin.db.session.commit",
            side_effect=IntegrityError(
                "INSERT",
                {},
                Exception("Duplicate class")
            )
        ), patch(
            "routes.academic_admin.db.session.rollback"
        ) as rollback:

            class_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                "/api/academic-admin/classes",
                json={
                    "course": "BCA",
                    "branch": "CSE",
                    "section": "A",
                    "admission_year": 2024
                }
            )

        self.assertEqual(response.status_code, 409)
        rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
