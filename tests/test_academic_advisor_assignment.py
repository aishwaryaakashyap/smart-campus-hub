import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from sqlalchemy.exc import SQLAlchemyError


class AcademicAdvisorAssignmentTests(unittest.TestCase):

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
        return SimpleNamespace(
            id=10,
            course="BCA",
            branch="CSE",
            section="A",
            admission_year=2024,
            advisor_user_id=None,
            advisor=None,
            is_active=is_active,
            created_at=None,
            updated_at=None
        )

    def advisor(self, role="advisor", status="active"):
        return SimpleNamespace(
            id=25,
            name="Test Advisor",
            email="advisor@example.com",
            role=role,
            account_status=status
        )

    def test_unauthenticated_user_cannot_list_advisors(self):
        response = self.client.get(
            "/api/academic-admin/advisors"
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_list_advisors(self):
        self.set_session(role="student")

        student = SimpleNamespace(
            role="student",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=student
        ):
            response = self.client.get(
                "/api/academic-admin/advisors"
            )

        self.assertEqual(response.status_code, 403)

    def test_coordinator_can_list_active_advisors(self):
        self.set_session()

        active_advisor = self.advisor()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.User.query"
        ) as user_query:

            user_query.filter_by.return_value.order_by.return_value.all.return_value = [
                active_advisor
            ]

            response = self.client.get(
                "/api/academic-admin/advisors"
            )

        self.assertEqual(response.status_code, 200)

        result = response.get_json()

        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["advisors"],
            [{
                "id": 25,
                "name": "Test Advisor",
                "email": "advisor@example.com",
                "account_status": "active"
            }]
        )

        user_query.filter_by.assert_called_once_with(
            role="advisor",
            account_status="active"
        )

    def test_unauthenticated_user_cannot_assign_advisor(self):
        response = self.client.put(
            "/api/academic-admin/classes/10/advisor",
            json={"advisor_user_id": 25}
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_assign_advisor(self):
        self.set_session(role="student")

        student = SimpleNamespace(
            role="student",
            account_status="active"
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=student
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 403)

    def test_missing_advisor_user_id_is_rejected(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={}
            )

        self.assertEqual(response.status_code, 400)

    def test_invalid_advisor_user_ids_are_rejected(self):
        self.set_session()

        invalid_ids = [
            True,
            False,
            "25",
            0,
            -1,
            1.5
        ]

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ):
            for invalid_id in invalid_ids:
                with self.subTest(advisor_user_id=invalid_id):
                    response = self.client.put(
                        "/api/academic-admin/classes/10/advisor",
                        json={"advisor_user_id": invalid_id}
                    )

                    self.assertEqual(response.status_code, 400)

    def test_assignment_to_nonexistent_class_returns_404(self):
        self.set_session()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=None
        ):
            response = self.client.put(
                "/api/academic-admin/classes/999/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 404)

    def test_archived_class_cannot_receive_advisor_assignment(self):
        self.set_session()
        archived_class = self.academic_class(is_active=False)

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=archived_class
        ) as get_record:

            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(get_record.call_count, 1)

    def test_nonexistent_advisor_returns_404(self):
        self.set_session()
        academic_class = self.academic_class()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, None]
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 999}
            )

        self.assertEqual(response.status_code, 404)

    def test_non_advisor_account_cannot_be_assigned(self):
        self.set_session()
        academic_class = self.academic_class()
        student_account = self.advisor(role="student")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, student_account]
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 409)

    def test_pending_advisor_cannot_be_assigned(self):
        self.set_session()
        academic_class = self.academic_class()
        pending_advisor = self.advisor(status="pending")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, pending_advisor]
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 409)

    def test_deactivated_advisor_cannot_be_assigned(self):
        self.set_session()
        academic_class = self.academic_class()
        inactive_advisor = self.advisor(status="deactivated")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, inactive_advisor]
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 409)

    def test_active_advisor_can_be_assigned(self):
        self.set_session()

        academic_class = self.academic_class()
        active_advisor = self.advisor()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, active_advisor]
        ), patch(
            "routes.academic_admin.record_activity"
        ) as activity, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit, patch(
            "routes.academic_admin.serialize_academic_class",
            return_value={
                "id": 10,
                "advisor_user_id": 25
            }
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Advisor assigned successfully"
        )
        self.assertEqual(academic_class.advisor_user_id, 25)
        self.assertIs(academic_class.advisor, active_advisor)
        activity.assert_called_once_with(
            actor_user_id=1,
            target_user_id=25,
            action="class_advisor_assigned",
            entity_type="academic_class",
            entity_id=10,
            description="Coordinator assigned Advisor 25 to academic class 10"
        )
        commit.assert_called_once()

    def test_coordinator_can_replace_advisor_when_students_are_linked(self):
        self.set_session()

        old_advisor = self.advisor()
        new_advisor = SimpleNamespace(
            id=26,
            name="Replacement Advisor",
            email="replacement@example.com",
            role="advisor",
            account_status="active"
        )

        academic_class = self.academic_class()
        academic_class.advisor_user_id = old_advisor.id
        academic_class.advisor = old_advisor

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, new_advisor]
        ), patch(
            "routes.academic_admin.record_activity"
        ) as activity, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit, patch(
            "routes.academic_admin.serialize_academic_class",
            return_value={
                "id": 10,
                "advisor_user_id": 26
            }
        ):
            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 26}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Advisor assigned successfully"
        )
        self.assertEqual(academic_class.advisor_user_id, 26)
        self.assertIs(academic_class.advisor, new_advisor)
        activity.assert_called_once_with(
            actor_user_id=1,
            target_user_id=26,
            action="class_advisor_changed",
            entity_type="academic_class",
            entity_id=10,
            description=(
                "Coordinator changed Advisor for academic class 10 "
                "from 25 to 26"
            )
        )
        commit.assert_called_once()

    def test_coordinator_can_remove_advisor_assignment(self):
        self.set_session()

        academic_class = self.academic_class()
        academic_class.advisor_user_id = 25
        academic_class.advisor = self.advisor()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.Student.query"
        ) as student_query, patch(
            "routes.academic_admin.record_activity"
        ) as activity, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit, patch(
            "routes.academic_admin.serialize_academic_class",
            return_value={
                "id": 10,
                "advisor_user_id": None
            }
        ):
            student_query.filter_by.return_value.first.return_value = None

            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": None}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Advisor assignment removed successfully"
        )
        self.assertIsNone(academic_class.advisor_user_id)
        self.assertIsNone(academic_class.advisor)
        activity.assert_called_once_with(
            actor_user_id=1,
            target_user_id=25,
            action="class_advisor_removed",
            entity_type="academic_class",
            entity_id=10,
            description="Coordinator removed Advisor 25 from academic class 10"
        )
        commit.assert_called_once()

    def test_coordinator_cannot_remove_advisor_when_students_are_linked(self):
        self.set_session()

        academic_class = self.academic_class()
        academic_class.advisor_user_id = 25
        academic_class.advisor = self.advisor()

        linked_student = SimpleNamespace(
            id=101,
            academic_class_id=10
        )

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            return_value=academic_class
        ), patch(
            "routes.academic_admin.Student.query"
        ) as student_query, patch(
            "routes.academic_admin.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.first.return_value = linked_student

            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": None}
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("linked students", response.get_json()["error"])
        self.assertEqual(academic_class.advisor_user_id, 25)
        self.assertIsNotNone(academic_class.advisor)
        commit.assert_not_called()

    def test_database_error_rolls_back_assignment(self):
        self.set_session()

        academic_class = self.academic_class()
        active_advisor = self.advisor()

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator()
        ), patch(
            "routes.academic_admin.db.session.get",
            side_effect=[academic_class, active_advisor]
        ), patch(
            "routes.academic_admin.db.session.commit",
            side_effect=SQLAlchemyError("Database error")
        ), patch(
            "routes.academic_admin.db.session.rollback"
        ) as rollback:

            response = self.client.put(
                "/api/academic-admin/classes/10/advisor",
                json={"advisor_user_id": 25}
            )

        self.assertEqual(response.status_code, 500)
        rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
