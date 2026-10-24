import unittest
from unittest.mock import MagicMock, patch

from app import app


class SkillGapRouteTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def set_session(self, user_id=1, role="student"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_rejects_unauthenticated_request(self):
        response = self.client.get("/api/skill-gap/1")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_rejects_non_student_role(self):
        self.set_session(role="coordinator")

        response = self.client.get("/api/skill-gap/1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only students can view their skill gap",
        )

    @patch("routes.skill_gap.Student.query")
    def test_returns_404_when_student_profile_missing(self, student_query):
        self.set_session()

        student_query.filter_by.return_value.first.return_value = None

        response = self.client.get("/api/skill-gap/1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Student profile not found",
        )

    @patch("routes.skill_gap.PlacementDrive.query")
    @patch("routes.skill_gap.Student.query")
    def test_returns_404_when_drive_missing(
        self, student_query, drive_query
    ):
        self.set_session()

        student = MagicMock()
        student.id = 10

        student_query.filter_by.return_value.first.return_value = student
        drive_query.get.return_value = None

        response = self.client.get("/api/skill-gap/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Placement drive not found",
        )

    @patch("routes.skill_gap.analyze_skill_gap")
    @patch("routes.skill_gap.Skill.query")
    @patch("routes.skill_gap.StudentSkill.query")
    @patch("routes.skill_gap.PlacementDrive.query")
    @patch("routes.skill_gap.Student.query")
    def test_returns_skill_gap_for_student(
        self,
        student_query,
        drive_query,
        student_skill_query,
        skill_query,
        analyze_mock,
    ):
        self.set_session()

        student = MagicMock()
        student.id = 10

        drive = MagicMock()
        drive.id = 5
        drive.job_role = "Python Developer"
        drive.job_description = "Python and SQL required"

        student_query.filter_by.return_value.first.return_value = student
        drive_query.get.return_value = drive
        student_skill_query.filter_by.return_value.all.return_value = []

        skill = MagicMock()
        skill.name = "Python"
        skill_query.all.return_value = [skill]

        analyze_mock.return_value = {
            "required_skills": ["Python"],
            "matched_skills": ["Python"],
            "missing_skills": [],
            "total_required_skills": 1,
            "match_percentage": 100.0,
            "method": "Rule-based matching against the existing skill catalog",
        }

        response = self.client.get("/api/skill-gap/5")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["student_id"], 10)
        self.assertEqual(data["drive_id"], 5)
        self.assertEqual(data["job_role"], "Python Developer")
        self.assertEqual(data["matched_skills"], ["Python"])
        self.assertEqual(data["match_percentage"], 100.0)

        analyze_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
