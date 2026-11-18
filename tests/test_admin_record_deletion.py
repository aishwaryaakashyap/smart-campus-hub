import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from extensions import db
from models import User


class AdminRecordDeletionTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        self.context = app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)

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

    def test_deactivated_advisor_without_references_can_be_deleted(self):
        advisor = SimpleNamespace(
            id=41,
            account_status=User.STATUS_DEACTIVATED
        )

        with (
            patch(
                "routes.advisor_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.advisor_admin.get_advisor_account",
                return_value=advisor
            ),
            patch(
                "routes.advisor_admin.find_referencing_records",
                return_value=[]
            ),
            patch(
                "routes.advisor_admin.PasswordResetToken"
            ) as token_model,
            patch.object(db.session, "delete") as delete_record,
            patch.object(db.session, "commit") as commit
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/41/delete"
            )

        self.assertEqual(response.status_code, 200)
        delete_record.assert_called_once_with(advisor)
        commit.assert_called_once()
        token_model.query.filter_by.assert_called_once_with(user_id=41)

    def test_active_advisor_cannot_be_deleted(self):
        advisor = SimpleNamespace(
            id=41,
            account_status=User.STATUS_ACTIVE
        )

        with (
            patch(
                "routes.advisor_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.advisor_admin.get_advisor_account",
                return_value=advisor
            ),
            patch(
                "routes.advisor_admin.find_referencing_records"
            ) as reference_check,
            patch.object(db.session, "delete") as delete_record
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/41/delete"
            )

        self.assertEqual(response.status_code, 409)
        reference_check.assert_not_called()
        delete_record.assert_not_called()

    def test_advisor_with_linked_records_cannot_be_deleted(self):
        advisor = SimpleNamespace(
            id=41,
            account_status=User.STATUS_DEACTIVATED
        )

        references = [{
            "table": "grievances",
            "column": "assigned_to",
            "count": 2
        }]

        with (
            patch(
                "routes.advisor_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.advisor_admin.get_advisor_account",
                return_value=advisor
            ),
            patch(
                "routes.advisor_admin.find_referencing_records",
                return_value=references
            ),
            patch.object(db.session, "delete") as delete_record,
            patch.object(db.session, "commit") as commit
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/41/delete"
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["references"], references)
        delete_record.assert_not_called()
        commit.assert_not_called()

    def test_archived_class_without_references_can_be_deleted(self):
        academic_class = SimpleNamespace(
            id=52,
            is_active=False
        )

        with (
            patch(
                "routes.academic_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.academic_admin.db.session.get",
                return_value=academic_class
            ),
            patch(
                "routes.academic_admin.find_referencing_records",
                return_value=[]
            ),
            patch.object(db.session, "delete") as delete_record,
            patch.object(db.session, "commit") as commit
        ):
            response = self.client.delete(
                "/api/academic-admin/classes/52/delete"
            )

        self.assertEqual(response.status_code, 200)
        delete_record.assert_called_once_with(academic_class)
        commit.assert_called_once()

    def test_active_class_cannot_be_deleted(self):
        academic_class = SimpleNamespace(
            id=52,
            is_active=True
        )

        with (
            patch(
                "routes.academic_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.academic_admin.db.session.get",
                return_value=academic_class
            ),
            patch(
                "routes.academic_admin.find_referencing_records"
            ) as reference_check,
            patch.object(db.session, "delete") as delete_record
        ):
            response = self.client.delete(
                "/api/academic-admin/classes/52/delete"
            )

        self.assertEqual(response.status_code, 409)
        reference_check.assert_not_called()
        delete_record.assert_not_called()

    def test_class_with_student_records_cannot_be_deleted(self):
        academic_class = SimpleNamespace(
            id=52,
            is_active=False
        )

        references = [{
            "table": "students",
            "column": "academic_class_id",
            "count": 3
        }]

        with (
            patch(
                "routes.academic_admin.require_coordinator",
                return_value=None
            ),
            patch(
                "routes.academic_admin.db.session.get",
                return_value=academic_class
            ),
            patch(
                "routes.academic_admin.find_referencing_records",
                return_value=references
            ),
            patch.object(db.session, "delete") as delete_record,
            patch.object(db.session, "commit") as commit
        ):
            response = self.client.delete(
                "/api/academic-admin/classes/52/delete"
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["references"], references)
        delete_record.assert_not_called()
        commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
