import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class SkillRouteAuthorizationTests(unittest.TestCase):

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

    def set_session(self, user_id=1, role="student"):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = user_id
            current_session["role"] = role

    def assert_session_cleared(self):
        with self.client.session_transaction() as current_session:
            self.assertNotIn("user_id", current_session)
            self.assertNotIn("role", current_session)

    def test_unauthenticated_user_cannot_add_skill(self):
        response = self.client.post(
            "/api/skills/",
            json={"name": "Python"}
        )

        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_user_cannot_access_my_skills(self):
        response = self.client.get("/api/skills/my-skills")

        self.assertEqual(response.status_code, 401)

    def test_student_cannot_add_catalogue_skill(self):
        self.set_session(role="student")

        with patch(
            "routes.skill.get_session_user",
            return_value=SimpleNamespace(role="student")
        ):
            response = self.client.post(
                "/api/skills/",
                json={"name": "Python"}
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can perform this action"
        )

    def test_stale_coordinator_session_is_cleared_after_role_change(self):
        self.set_session(user_id=20, role="coordinator")

        changed_user = SimpleNamespace(role="student")

        with patch(
            "routes.skill.get_session_user",
            return_value=changed_user
        ):
            response = self.client.post(
                "/api/skills/",
                json={"name": "Python"}
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")
        self.assert_session_cleared()

    def test_stale_student_session_is_cleared_after_role_change(self):
        self.set_session(user_id=30, role="student")

        changed_user = SimpleNamespace(role="coordinator")

        with patch(
            "routes.skill.get_session_user",
            return_value=changed_user
        ):
            response = self.client.get("/api/skills/my-skills")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")
        self.assert_session_cleared()

    def test_missing_account_clears_coordinator_session(self):
        self.set_session(user_id=99, role="coordinator")

        with patch(
            "routes.skill.get_session_user",
            return_value=None
        ):
            response = self.client.post(
                "/api/skills/",
                json={"name": "Python"}
            )

        self.assertEqual(response.status_code, 401)
        self.assert_session_cleared()

    def test_student_without_profile_receives_404(self):
        self.set_session(user_id=30, role="student")

        with patch(
            "routes.skill.get_session_user",
            return_value=SimpleNamespace(role="student")
        ), patch(
            "routes.skill.Student.query"
        ) as student_query:

            student_query.filter_by.return_value.first.return_value = None

            response = self.client.get("/api/skills/my-skills")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Student profile not found. Create your profile first."
        )

    def test_public_skill_catalogue_remains_accessible(self):
        with patch(
            "routes.skill.Skill.query"
        ) as skill_query:

            skill_query.all.return_value = []

            response = self.client.get("/api/skills/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])


if __name__ == "__main__":
    unittest.main()
