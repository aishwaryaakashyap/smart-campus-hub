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


class TestCoordinatorSkillGapRoute(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()

    def set_session(self, user_id=2, role="coordinator"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_unauthenticated_access_returns_401(self):
        response = self.client.get("/api/skill-gap/coordinator/5")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_student_access_returns_403(self):
        self.set_session(user_id=10, role="student")

        response = self.client.get("/api/skill-gap/coordinator/5")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only coordinators can view overall skill gap analysis"
        )

    def test_missing_coordinator_account_returns_401_and_clears_session(self):
        self.set_session()

        with patch("routes.skill_gap.db.session.get", return_value=None):
            response = self.client.get("/api/skill-gap/coordinator/5")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()["error"],
            "Invalid coordinator session"
        )

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_non_coordinator_database_role_returns_401(self):
        self.set_session()

        invalid_user = MagicMock()
        invalid_user.role = "student"

        with patch(
            "routes.skill_gap.db.session.get",
            return_value=invalid_user
        ):
            response = self.client.get("/api/skill-gap/coordinator/5")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()["error"],
            "Invalid coordinator session"
        )

    def test_missing_drive_returns_404(self):
        self.set_session()

        with patch("routes.skill_gap.db.session.get") as user_get, \
             patch("routes.skill_gap.PlacementDrive.query") as drive_query:

            coordinator = MagicMock()
            coordinator.role = "coordinator"
            user_get.return_value = coordinator
            drive_query.get.return_value = None

            response = self.client.get("/api/skill-gap/coordinator/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Placement drive not found"
        )

    def test_coordinator_receives_aggregate_skill_gap_analysis(self):
        self.set_session()

        drive = MagicMock()
        drive.id = 5
        drive.job_role = "Python Developer"
        drive.job_description = "Python, SQL and Java are required."

        company = MagicMock()
        company.name = "Test Company"
        drive.company = company

        students = []
        for student_id in [10, 11, 12]:
            student = MagicMock()
            student.id = student_id
            students.append(student)

        python = MagicMock()
        python.name = "Python"

        sql = MagicMock()
        sql.name = "SQL"

        java = MagicMock()
        java.name = "Java"

        skills = [python, sql, java]

        entries = []

        def make_entry(student_id, skill, proficiency):
            entry = MagicMock()
            entry.student_id = student_id
            entry.skill = skill
            entry.proficiency = proficiency
            return entry

        entries.append(make_entry(10, python, "Advanced"))
        entries.append(make_entry(10, sql, "Intermediate"))
        entries.append(make_entry(11, python, "Beginner"))

        with patch("routes.skill_gap.db.session.get") as user_get, \
             patch("routes.skill_gap.PlacementDrive.query") as drive_query, \
             patch("routes.skill_gap.Student.query") as student_query, \
             patch("routes.skill_gap.Skill.query") as skill_query, \
             patch("routes.skill_gap.StudentSkill.query") as student_skill_query:

            coordinator = MagicMock()
            coordinator.role = "coordinator"
            user_get.return_value = coordinator

            drive_query.get.return_value = drive
            student_query.all.return_value = students
            skill_query.all.return_value = skills
            student_skill_query.all.return_value = entries

            response = self.client.get("/api/skill-gap/coordinator/5")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(data["drive_id"], 5)
        self.assertEqual(data["job_role"], "Python Developer")
        self.assertEqual(data["company_name"], "Test Company")
        self.assertEqual(data["total_students"], 3)
        self.assertEqual(data["total_required_skills"], 3)
        self.assertEqual(data["overall_skill_readiness"], 33.33)

        report = {
            item["skill_name"]: item
            for item in data["skill_report"]
        }

        self.assertEqual(report["Python"]["students_with_skill"], 2)
        self.assertEqual(report["Python"]["students_missing_skill"], 1)
        self.assertEqual(
            report["Python"]["proficiency_counts"]["Advanced"], 1
        )
        self.assertEqual(
            report["Python"]["proficiency_counts"]["Beginner"], 1
        )

        self.assertEqual(report["SQL"]["students_with_skill"], 1)
        self.assertEqual(report["SQL"]["students_missing_skill"], 2)
        self.assertEqual(
            report["SQL"]["proficiency_counts"]["Intermediate"], 1
        )

        self.assertEqual(report["Java"]["students_with_skill"], 0)
        self.assertEqual(report["Java"]["students_missing_skill"], 3)


if __name__ == "__main__":
    unittest.main()
