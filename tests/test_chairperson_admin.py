import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class ChairpersonAdminTests(unittest.TestCase):

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

        self.coordinator = SimpleNamespace(
            id=1,
            role="coordinator",
            account_status="active"
        )

        self.set_session()

        self.auth_patch = patch(
            "routes.academic_admin.get_session_user",
            return_value=self.coordinator
        )
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = user_id
            current_session["role"] = role

    def chairperson(self, status="pending", chairperson_id=20):
        return SimpleNamespace(
            id=chairperson_id,
            name="Test Chairperson",
            email="chairperson@example.com",
            role="chairperson",
            account_status=status,
            created_at=None,
            reviewed_by_user_id=None,
            reviewed_by=None,
            reviewed_at=None,
            rejection_reason=None
        )

    def settings(self, primary_id=None):
        return SimpleNamespace(
            singleton_id=1,
            primary_chairperson_user_id=primary_id,
            updated_by_user_id=None
        )

    def serializer_patch(self):
        return patch(
            "routes.chairperson_admin.serialize_chairperson",
            side_effect=lambda account, primary_id=None: {
                "id": account.id,
                "name": account.name,
                "email": account.email,
                "role": account.role,
                "account_status": account.account_status,
                "is_primary": account.id == primary_id,
                "reviewed_by_user_id": account.reviewed_by_user_id,
                "rejection_reason": account.rejection_reason
            }
        )

    def test_student_cannot_list_chairpersons(self):
        self.set_session(role="student")

        with patch(
            "routes.academic_admin.get_session_user",
            return_value=SimpleNamespace(
                role="student",
                account_status="active"
            )
        ):
            response = self.client.get(
                "/api/academic-admin/chairpersons"
            )

        self.assertEqual(response.status_code, 403)

    def test_list_chairpersons_includes_primary_selection(self):
        account = self.chairperson(status="active")

        with patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings(primary_id=20)
        ), patch(
            "routes.chairperson_admin.User.query"
        ) as user_query, self.serializer_patch():

            user_query.filter_by.return_value.order_by.return_value.all.return_value = [
                account
            ]

            response = self.client.get(
                "/api/academic-admin/chairpersons"
            )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["primary_chairperson_user_id"], 20)
        self.assertTrue(result["chairpersons"][0]["is_primary"])

    def test_list_chairpersons_filters_by_status(self):
        account = self.chairperson(status="pending")

        with patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings()
        ), patch(
            "routes.chairperson_admin.User.query"
        ) as user_query, self.serializer_patch():

            user_query.filter_by.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
                account
            ]

            response = self.client.get(
                "/api/academic-admin/chairpersons?status=pending"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 1)

        user_query.filter_by.assert_called_once_with(role="chairperson")
        user_query.filter_by.return_value.filter_by.assert_called_once_with(
            account_status="pending"
        )

    def test_invalid_chairperson_status_filter_is_rejected(self):
        response = self.client.get(
            "/api/academic-admin/chairpersons?status=unknown"
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_settings_record_returns_503(self):
        with patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=None
        ):
            response = self.client.get(
                "/api/academic-admin/chairpersons"
            )

        self.assertEqual(response.status_code, 503)

    def test_create_chairperson_starts_pending(self):
        with patch(
            "routes.chairperson_admin.User.query"
        ) as user_query, patch(
            "routes.chairperson_admin.db.session.add"
        ) as add_record, patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, self.serializer_patch():

            user_query.filter_by.return_value.first.return_value = None

            def capture_account(account):
                account.id = 91

            add_record.side_effect = capture_account

            response = self.client.post(
                "/api/academic-admin/chairpersons",
                json={
                    "name": "New Chairperson",
                    "email": "NEW.CHAIRPERSON@example.com"
                }
            )

        self.assertEqual(response.status_code, 201)

        result = response.get_json()
        self.assertEqual(result["chairperson"]["id"], 91)
        self.assertEqual(result["chairperson"]["role"], "chairperson")
        self.assertEqual(
            result["chairperson"]["account_status"],
            "pending"
        )
        self.assertNotIn("password_hash", result["chairperson"])
        self.assertNotIn("password", str(result).lower())

        created = add_record.call_args.args[0]
        self.assertEqual(
            created.email,
            "new.chairperson@example.com"
        )
        self.assertTrue(created.password_hash)
        self.assertFalse(
            created.check_password("KnownTemporaryPassword123")
        )

        commit.assert_called_once()

    def test_duplicate_chairperson_email_is_rejected(self):
        with patch(
            "routes.chairperson_admin.User.query"
        ) as user_query:

            user_query.filter_by.return_value.first.return_value = object()

            response = self.client.post(
                "/api/academic-admin/chairpersons",
                json={
                    "name": "Duplicate Chairperson",
                    "email": "existing@example.com"
                }
            )

        self.assertEqual(response.status_code, 409)

    def test_invalid_chairperson_creation_is_rejected(self):
        response = self.client.post(
            "/api/academic-admin/chairpersons",
            json={"name": "Missing Email"}
        )

        self.assertEqual(response.status_code, 400)

    def test_coordinator_can_approve_pending_chairperson(self):
        account = self.chairperson()

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings()
        ), patch(
            "routes.chairperson_admin.create_chairperson_setup_token",
            return_value=("secret-chairperson-token", 15)
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, patch(
            "routes.chairperson_admin.send_chairperson_setup_link",
            return_value=True
        ) as send_email, self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/approve"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "active")
        self.assertEqual(account.reviewed_by_user_id, 1)
        self.assertIsNotNone(account.reviewed_at)
        self.assertTrue(response.get_json()["email_sent"])
        self.assertNotIn(
            "secret-chairperson-token",
            response.get_data(as_text=True)
        )
        send_email.assert_called_once()
        commit.assert_called_once()

    def test_approval_returns_202_when_setup_email_fails(self):
        account = self.chairperson()

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings()
        ), patch(
            "routes.chairperson_admin.create_chairperson_setup_token",
            return_value=("secret-chairperson-token", 15)
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ), patch(
            "routes.chairperson_admin.send_chairperson_setup_link",
            return_value=False
        ), self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/approve"
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(account.account_status, "active")
        self.assertFalse(response.get_json()["email_sent"])

    def test_active_chairperson_cannot_be_approved_again(self):
        account = self.chairperson(status="active")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ):
            response = self.client.post(
                "/api/academic-admin/chairpersons/20/approve"
            )

        self.assertEqual(response.status_code, 409)

    def test_coordinator_can_reject_pending_chairperson(self):
        account = self.chairperson()

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.invalidate_chairperson_setup_tokens"
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings()
        ), self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/reject",
                json={"reason": "Institutional approval not received"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "rejected")
        self.assertEqual(
            account.rejection_reason,
            "Institutional approval not received"
        )
        self.assertEqual(account.reviewed_by_user_id, 1)
        commit.assert_called_once()

    def test_deactivating_primary_chairperson_clears_selection(self):
        account = self.chairperson(status="active")
        settings = self.settings(primary_id=20)

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=settings
        ) as get_settings, patch(
            "routes.chairperson_admin.invalidate_chairperson_setup_tokens"
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/deactivate"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "deactivated")
        self.assertIsNone(settings.primary_chairperson_user_id)
        self.assertEqual(settings.updated_by_user_id, 1)
        get_settings.assert_called_once_with(lock=True)
        commit.assert_called_once()

    def test_deactivation_does_not_overwrite_rejection_reason(self):
        account = self.chairperson(
            status="active",
        )
        account.rejection_reason = "Previously recorded reason"

        settings = self.settings(primary_id=None)

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=settings
        ), patch(
            "routes.chairperson_admin.invalidate_chairperson_setup_tokens"
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ), self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/deactivate"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            account.rejection_reason,
            "Previously recorded reason"
        )

    def test_coordinator_can_reactivate_deactivated_chairperson(self):
        account = self.chairperson(status="deactivated")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=self.settings()
        ), self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/reactivate"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(account.account_status, "active")
        self.assertEqual(account.reviewed_by_user_id, 1)
        commit.assert_called_once()

    def test_only_active_chairperson_can_become_primary(self):
        account = self.chairperson(status="pending")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings"
        ) as get_settings:

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/primary"
            )

        self.assertEqual(response.status_code, 409)
        get_settings.assert_not_called()

    def test_coordinator_can_set_active_chairperson_as_primary(self):
        account = self.chairperson(status="active")
        settings = self.settings()

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=settings
        ) as get_settings, patch(
            "routes.chairperson_admin.db.session.commit"
        ) as commit, self.serializer_patch():

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/primary"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            settings.primary_chairperson_user_id,
            20
        )
        self.assertEqual(settings.updated_by_user_id, 1)
        self.assertEqual(
            response.get_json()["primary_chairperson_user_id"],
            20
        )
        get_settings.assert_called_once_with(lock=True)
        commit.assert_called_once()

    def test_primary_selection_requires_settings_record(self):
        account = self.chairperson(status="active")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.get_primary_settings",
            return_value=None
        ):
            response = self.client.post(
                "/api/academic-admin/chairpersons/20/primary"
            )

        self.assertEqual(response.status_code, 503)

    def test_active_chairperson_can_receive_setup_email(self):
        account = self.chairperson(status="active")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.create_chairperson_setup_token",
            return_value=("secret-chairperson-token", 15)
        ), patch(
            "routes.chairperson_admin.db.session.commit"
        ), patch(
            "routes.chairperson_admin.send_chairperson_setup_link",
            return_value=True
        ) as send_email:

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/setup-email"
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["email_sent"])
        self.assertNotIn(
            "secret-chairperson-token",
            response.get_data(as_text=True)
        )
        send_email.assert_called_once()

    def test_deactivated_chairperson_cannot_receive_setup_email(self):
        account = self.chairperson(status="deactivated")

        with patch(
            "routes.chairperson_admin.get_chairperson_account",
            return_value=account
        ), patch(
            "routes.chairperson_admin.send_chairperson_setup_link"
        ) as send_email:

            response = self.client.post(
                "/api/academic-admin/chairpersons/20/setup-email"
            )

        self.assertEqual(response.status_code, 409)
        send_email.assert_not_called()

    def test_unauthenticated_user_cannot_create_chairperson(self):
        with self.client.session_transaction() as current_session:
            current_session.clear()

        response = self.client.post(
            "/api/academic-admin/chairpersons",
            json={
                "name": "Test Chairperson",
                "email": "chairperson@example.com"
            }
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
