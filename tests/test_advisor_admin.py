import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from models import User


class AdvisorAdminTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        self.context = app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.addCleanup(
            app.config.__setitem__, "TESTING", self.previous_testing
        )
        self.addCleanup(
            app.config.__setitem__, "WTF_CSRF_ENABLED", self.previous_csrf
        )

        self.client = app.test_client()
        self.coordinator = SimpleNamespace(
            id=1,
            role="coordinator",
            account_status="active"
        )

        self.auth_patch = patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator
        )
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)

        self.set_session()

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = user_id
            current_session["role"] = role

    def advisor(
        self,
        advisor_id=20,
        status="pending",
        rejection_reason=None
    ):
        return SimpleNamespace(
            id=advisor_id,
            name="Test Advisor",
            email="advisor@example.com",
            role="advisor",
            account_status=status,
            created_at=None,
            reviewed_by_user_id=None,
            reviewed_by=None,
            reviewed_at=None,
            rejection_reason=rejection_reason
        )

    def serialize_patch(self):
        return patch(
            "routes.advisor_admin.serialize_advisor_account",
            side_effect=lambda account: {
                "id": account.id,
                "name": account.name,
                "email": account.email,
                "role": account.role,
                "account_status": account.account_status,
                "reviewed_by_user_id": account.reviewed_by_user_id,
                "reviewed_at": (
                    account.reviewed_at.isoformat()
                    if account.reviewed_at else None
                ),
                "rejection_reason": account.rejection_reason
            }
        )

    def test_student_cannot_list_advisor_accounts(self):
        self.set_session(role="student")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=SimpleNamespace(
                role="student",
                account_status="active"
            )
        ):
            response = self.client.get(
                "/api/academic-admin/advisors/accounts"
            )

        self.assertEqual(response.status_code, 403)

    def test_coordinator_can_list_advisor_accounts(self):
        with patch(
            "routes.advisor_admin.User.query"
        ) as user_query, self.serialize_patch():

            user_query.filter_by.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
                self.advisor()
            ]

            response = self.client.get(
                "/api/academic-admin/advisors/accounts?status=pending"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 1)
        user_query.filter_by.assert_called_once_with(
            role="advisor"
        )
        user_query.filter_by.return_value.filter_by.assert_called_once_with(
            account_status="pending"
        )

    def test_invalid_account_status_filter_is_rejected(self):
        response = self.client.get(
            "/api/academic-admin/advisors/accounts?status=unknown"
        )

        self.assertEqual(response.status_code, 400)

    def test_create_advisor_starts_in_pending_status(self):
        with patch(
            "routes.advisor_admin.User.query"
        ) as user_query, patch(
            "routes.advisor_admin.db.session.add"
        ) as add_record, patch(
            "routes.advisor_admin.db.session.commit"
        ) as commit, self.serialize_patch():

            user_query.filter_by.return_value.first.return_value = None

            def capture_advisor(account):
                account.id = 91

            add_record.side_effect = capture_advisor

            response = self.client.post(
                "/api/academic-admin/advisors",
                json={
                    "name": "New Advisor",
                    "email": "NEW.ADVISOR@example.com"
                }
            )

        self.assertEqual(response.status_code, 201)
        result = response.get_json()

        self.assertEqual(result["advisor"]["id"], 91)
        self.assertEqual(result["advisor"]["role"], "advisor")
        self.assertEqual(result["advisor"]["account_status"], "pending")
        self.assertNotIn("password", str(result).lower())
        self.assertNotIn("password_hash", result["advisor"])

        created = add_record.call_args.args[0]
        self.assertEqual(created.email, "new.advisor@example.com")
        self.assertTrue(created.password_hash)
        self.assertFalse(
            created.check_password("KnownTemporaryPassword123")
        )
        commit.assert_called_once()

    def test_duplicate_advisor_email_is_rejected(self):
        with patch(
            "routes.advisor_admin.User.query"
        ) as user_query:

            user_query.filter_by.return_value.first.return_value = object()

            response = self.client.post(
                "/api/academic-admin/advisors",
                json={
                    "name": "Duplicate Advisor",
                    "email": "existing@example.com"
                }
            )

        self.assertEqual(response.status_code, 409)

    def test_invalid_advisor_creation_payload_is_rejected(self):
        response = self.client.post(
            "/api/academic-admin/advisors",
            json={"name": "Missing Email"}
        )

        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_user_cannot_create_advisor(self):
        with self.client.session_transaction() as current_session:
            current_session.clear()

        response = self.client.post(
            "/api/academic-admin/advisors",
            json={
                "name": "New Advisor",
                "email": "new@example.com"
            }
        )

        self.assertEqual(response.status_code, 401)

    def test_coordinator_can_approve_pending_advisor(self):
        account = self.advisor(status="pending")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.create_setup_token",
            return_value=("secret-setup-token", 15)
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ) as commit, patch(
            "routes.advisor_admin.send_setup_link",
            return_value=True
        ) as send_email, self.serialize_patch():

            response = self.client.post(
                "/api/academic-admin/advisors/20/approve"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "active")
        self.assertEqual(account.reviewed_by_user_id, 1)
        self.assertIsNotNone(account.reviewed_at)
        self.assertTrue(response.get_json()["email_sent"])
        self.assertNotIn("secret-setup-token", response.get_data(as_text=True))
        send_email.assert_called_once()
        commit.assert_called_once()

    def test_approval_returns_202_when_setup_email_fails(self):
        account = self.advisor(status="pending")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.create_setup_token",
            return_value=("secret-setup-token", 15)
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ), patch(
            "routes.advisor_admin.send_setup_link",
            return_value=False
        ), self.serialize_patch():

            response = self.client.post(
                "/api/academic-admin/advisors/20/approve"
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(account.account_status, "active")
        self.assertFalse(response.get_json()["email_sent"])

    def test_already_active_advisor_cannot_be_approved_again(self):
        account = self.advisor(status="active")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/20/approve"
            )

        self.assertEqual(response.status_code, 409)

    def test_coordinator_can_reject_pending_advisor(self):
        account = self.advisor(status="pending")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.invalidate_unused_setup_tokens"
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ) as commit, self.serialize_patch():

            response = self.client.post(
                "/api/academic-admin/advisors/20/reject",
                json={"reason": "Institutional records not verified"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "rejected")
        self.assertEqual(
            account.rejection_reason,
            "Institutional records not verified"
        )
        self.assertEqual(account.reviewed_by_user_id, 1)
        commit.assert_called_once()

    def test_rejection_reason_must_be_text(self):
        account = self.advisor(status="pending")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/20/reject",
                json={"reason": 123}
            )

        self.assertEqual(response.status_code, 400)

    def test_coordinator_can_deactivate_active_advisor(self):
        account = self.advisor(
            status="active",
            rejection_reason="Previous rejection history"
        )

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.invalidate_unused_setup_tokens"
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ) as commit, self.serialize_patch():

            response = self.client.post(
                "/api/academic-admin/advisors/20/deactivate"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "deactivated")
        self.assertEqual(
            account.rejection_reason,
            "Previous rejection history"
        )
        self.assertIn(
            "preserved",
            response.get_json()["message"]
        )
        commit.assert_called_once()

    def test_coordinator_can_reactivate_deactivated_advisor(self):
        account = self.advisor(status="deactivated")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ) as commit, self.serialize_patch():

            response = self.client.post(
                "/api/academic-admin/advisors/20/reactivate"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "active")
        self.assertEqual(account.reviewed_by_user_id, 1)
        self.assertIsNone(account.rejection_reason)
        commit.assert_called_once()

    def test_only_deactivated_advisor_can_be_reactivated(self):
        account = self.advisor(status="pending")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ):
            response = self.client.post(
                "/api/academic-admin/advisors/20/reactivate"
            )

        self.assertEqual(response.status_code, 409)

    def test_coordinator_can_resend_setup_email(self):
        account = self.advisor(status="active")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.create_setup_token",
            return_value=("secret-setup-token", 15)
        ), patch(
            "routes.advisor_admin.db.session.commit"
        ), patch(
            "routes.advisor_admin.send_setup_link",
            return_value=True
        ) as send_email:

            response = self.client.post(
                "/api/academic-admin/advisors/20/setup-email"
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["email_sent"])
        self.assertNotIn("secret-setup-token", response.get_data(as_text=True))
        send_email.assert_called_once()

    def test_deactivated_advisor_cannot_receive_setup_email(self):
        account = self.advisor(status="deactivated")

        with patch(
            "routes.advisor_admin.get_advisor_account",
            return_value=account
        ), patch(
            "routes.advisor_admin.send_setup_link"
        ) as send_email:

            response = self.client.post(
                "/api/academic-admin/advisors/20/setup-email"
            )

        self.assertEqual(response.status_code, 409)
        send_email.assert_not_called()

    def test_pending_account_cannot_log_in(self):
        account = SimpleNamespace(
            account_status="pending",
            check_password=lambda password: True
        )

        with patch(
            "routes.auth.User.query"
        ) as user_query:

            user_query.filter_by.return_value.first.return_value = account

            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": "pending@example.com",
                    "password": "TestPassword123"
                }
            )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("user_id", response.get_json())

    def test_deactivated_advisor_session_cannot_manage_grievances(self):
        self.set_session(user_id=20, role="advisor")

        inactive_advisor = SimpleNamespace(
            id=20,
            role="advisor",
            account_status="deactivated"
        )

        with patch(
            "routes.grievance.get_session_user",
            return_value=inactive_advisor
        ):
            response = self.client.get("/api/grievances/manage")

        self.assertEqual(response.status_code, 401)

        with self.client.session_transaction() as current_session:
            self.assertNotIn("user_id", current_session)
            self.assertNotIn("role", current_session)


if __name__ == "__main__":
    unittest.main()
