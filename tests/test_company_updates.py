import unittest
from types import SimpleNamespace
from unittest.mock import patch, call

from app import app


class CompanyUpdateTests(unittest.TestCase):

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

    def set_session(self, user_id=1, role="coordinator"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_unauthenticated_user_cannot_publish_update(self):
        response = self.client.post(
            "/api/updates/",
            json={
                "company_id": 1,
                "title": "Placement update",
                "message": "The deadline has changed."
            }
        )

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_publish_update(self):
        self.set_session(role="student")

        with patch("routes.company_update.db.session.get") as get_company:
            response = self.client.post(
                "/api/updates/",
                json={
                    "company_id": 1,
                    "title": "Placement update",
                    "message": "The deadline has changed."
                }
            )

        self.assertEqual(response.status_code, 403)
        get_company.assert_not_called()

    def test_publishing_update_notifies_all_students(self):
        self.set_session(user_id=20, role="coordinator")

        company = SimpleNamespace(name="Google")
        students = [
            SimpleNamespace(id=101),
            SimpleNamespace(id=102)
        ]

        update = SimpleNamespace(
            id=8,
            title="Hiring update",
            message="The application deadline has been extended."
        )

        with patch(
            "routes.company_update.db.session.get",
            return_value=company
        ), patch(
            "routes.company_update.CompanyUpdate",
            return_value=update
        ) as update_model, patch(
            "routes.company_update.User.query"
        ) as user_query, patch(
            "routes.company_update.create_notification"
        ) as notify, patch(
            "routes.company_update.db.session.add"
        ) as add, patch(
            "routes.company_update.db.session.commit"
        ) as commit:

            user_query.filter_by.return_value.all.return_value = students

            response = self.client.post(
                "/api/updates/",
                json={
                    "company_id": 5,
                    "title": "Hiring update",
                    "message": "The application deadline has been extended."
                }
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["id"], 8)

        update_model.assert_called_once_with(
            company_id=5,
            title="Hiring update",
            message="The application deadline has been extended."
        )

        user_query.filter_by.assert_called_once_with(role="student")

        self.assertEqual(notify.call_count, 2)
        notify.assert_has_calls([
            call(
                user_id=101,
                title="New Company Update: Google",
                message=(
                    "Hiring update: "
                    "The application deadline has been extended."
                ),
                notification_type="company_update"
            ),
            call(
                user_id=102,
                title="New Company Update: Google",
                message=(
                    "Hiring update: "
                    "The application deadline has been extended."
                ),
                notification_type="company_update"
            )
        ])

        add.assert_called_once_with(update)
        commit.assert_called_once()

    def test_notification_failure_rolls_back_update(self):
        self.set_session(user_id=20, role="coordinator")

        company = SimpleNamespace(name="Google")
        update = SimpleNamespace(
            id=9,
            title="Hiring update",
            message="The deadline has changed."
        )
        students = [SimpleNamespace(id=101)]

        with patch(
            "routes.company_update.db.session.get",
            return_value=company
        ), patch(
            "routes.company_update.CompanyUpdate",
            return_value=update
        ), patch(
            "routes.company_update.User.query"
        ) as user_query, patch(
            "routes.company_update.create_notification",
            side_effect=RuntimeError("Notification failed")
        ) as notify, patch(
            "routes.company_update.db.session.add"
        ) as add, patch(
            "routes.company_update.db.session.commit"
        ) as commit, patch(
            "routes.company_update.db.session.rollback"
        ) as rollback:

            user_query.filter_by.return_value.all.return_value = students

            response = self.client.post(
                "/api/updates/",
                json={
                    "company_id": 5,
                    "title": "Hiring update",
                    "message": "The deadline has changed."
                }
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json()["error"],
            "Unable to post company update"
        )
        notify.assert_called_once_with(
            user_id=101,
            title="New Company Update: Google",
            message="Hiring update: The deadline has changed.",
            notification_type="company_update"
        )
        add.assert_called_once_with(update)
        commit.assert_not_called()
        rollback.assert_called_once()

    def test_unauthenticated_user_cannot_read_company_updates(self):
        all_updates = self.client.get("/api/updates/")
        company_updates = self.client.get("/api/updates/company/5")

        self.assertEqual(all_updates.status_code, 401)
        self.assertEqual(company_updates.status_code, 401)

    def test_stale_session_cannot_read_company_updates(self):
        self.set_session(user_id=999, role="student")

        with patch(
            "routes.company_update.db.session.get",
            return_value=None
        ):
            response = self.client.get("/api/updates/")

        self.assertEqual(response.status_code, 401)

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)
            self.assertNotIn("role", session)

    def test_authenticated_student_can_read_all_updates(self):
        self.set_session(user_id=101, role="student")

        with patch(
            "routes.company_update.db.session.get",
            return_value=SimpleNamespace(id=101)
        ), patch(
            "routes.company_update.CompanyUpdate.query"
        ) as update_query:

            update_query.order_by.return_value.all.return_value = []

            response = self.client.get("/api/updates/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_authenticated_student_can_read_company_updates(self):
        self.set_session(user_id=101, role="student")

        user = SimpleNamespace(id=101)
        company = SimpleNamespace(id=5)

        with patch(
            "routes.company_update.db.session.get",
            side_effect=[user, company]
        ), patch(
            "routes.company_update.CompanyUpdate.query"
        ) as update_query:

            update_query.filter_by.return_value.order_by.return_value.all.return_value = []

            response = self.client.get("/api/updates/company/5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_company_updates_return_404_for_unknown_company(self):
        self.set_session(user_id=101, role="student")

        with patch(
            "routes.company_update.db.session.get",
            side_effect=[
                SimpleNamespace(id=101),
                None
            ]
        ):
            response = self.client.get("/api/updates/company/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Company not found"
        )


if __name__ == "__main__":
    unittest.main()
