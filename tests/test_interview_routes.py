import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class InterviewRouteAccessTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()
        app.config["TESTING"] = self.previous_testing
        app.config["WTF_CSRF_ENABLED"] = self.previous_csrf

    def set_session(self, user_id=1, role="student"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def create_experience(self):
        answer = SimpleNamespace(
            student_answer="Python is an interpreted language.",
            answer_status="Correct",
            reference_answer="Python is a high-level programming language."
        )

        question = SimpleNamespace(
            question_text="What is Python?",
            topic="Python",
            difficulty="Easy",
            answers=[answer]
        )

        interview_round = SimpleNamespace(
            round_number=1,
            round_type="Technical",
            mode="Online",
            duration_minutes=30,
            difficulty="Medium",
            remarks="Technical discussion",
            questions=[question]
        )

        skill = SimpleNamespace(
            skill_name="Python",
            importance_rating=4
        )

        resource = SimpleNamespace(
            resource_type="Article",
            resource_name="Python Documentation",
            url="https://docs.python.org/",
            description="Official Python documentation"
        )

        return SimpleNamespace(
            id=1,
            company=SimpleNamespace(name="Google"),
            job_role="Software Engineer",
            year=2026,
            selection_status="Selected",
            overall_difficulty="Medium",
            preparation_summary="Practised Python and DBMS.",
            selection_factors="Technical preparation",
            rounds=[interview_round],
            skills=[skill],
            resources=[resource]
        )

    def test_company_experiences_reject_unauthenticated_user(self):
        with patch("routes.interview.Company.query") as company_query, \
             patch("routes.interview.InterviewExperience.query") as experience_query:

            response = self.client.get("/api/interviews/company/1")

            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()["error"], "Not logged in")

            company_query.get.assert_not_called()
            experience_query.filter_by.assert_not_called()

    def test_interview_details_reject_unauthenticated_user(self):
        with patch("routes.interview.InterviewExperience.query") as experience_query:

            response = self.client.get("/api/interviews/1")

            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()["error"], "Not logged in")

            experience_query.get.assert_not_called()

    def test_company_experiences_reject_coordinator(self):
        self.set_session(role="coordinator")

        with patch("routes.interview.Company.query") as company_query, \
             patch("routes.interview.InterviewExperience.query") as experience_query:

            response = self.client.get("/api/interviews/company/1")

            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.get_json()["error"],
                "Only students can perform this action"
            )

            company_query.get.assert_not_called()
            experience_query.filter_by.assert_not_called()

    def test_interview_details_reject_coordinator(self):
        self.set_session(role="coordinator")

        with patch("routes.interview.InterviewExperience.query") as experience_query:

            response = self.client.get("/api/interviews/1")

            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.get_json()["error"],
                "Only students can perform this action"
            )

            experience_query.get.assert_not_called()

    def test_student_without_profile_cannot_view_company_experiences(self):
        self.set_session(role="student")

        with patch("routes.interview.Student.query") as student_query, \
             patch("routes.interview.Company.query") as company_query:

            student_query.filter_by.return_value.first.return_value = None

            response = self.client.get("/api/interviews/company/1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "Student profile not found. Create your profile first."
        )
        company_query.get.assert_not_called()

    def test_student_can_view_company_experiences(self):
        self.set_session(role="student")

        company = SimpleNamespace(name="Google")
        experience = SimpleNamespace(
            id=1,
            job_role="Software Engineer",
            year=2026,
            selection_status="Selected",
            overall_difficulty="Medium",
            rounds=[SimpleNamespace(round_number=1)]
        )

        with patch("routes.interview.Student.query") as student_query, \
             patch("routes.interview.Company.query") as company_query, \
             patch("routes.interview.InterviewExperience.query") as experience_query:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=1)
            )
            company_query.get.return_value = company
            experience_query.filter_by.return_value.all.return_value = [
                experience
            ]

            response = self.client.get("/api/interviews/company/1")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["job_role"], "Software Engineer")
        self.assertEqual(data[0]["round_count"], 1)

    def test_student_can_view_interview_details(self):
        self.set_session(role="student")
        experience = self.create_experience()

        with patch("routes.interview.Student.query") as student_query, \
             patch("routes.interview.InterviewExperience.query") as experience_query:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=1)
            )
            experience_query.get.return_value = experience

            response = self.client.get("/api/interviews/1")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(data["company_name"], "Google")
        self.assertEqual(data["job_role"], "Software Engineer")
        self.assertEqual(
            data["rounds"][0]["questions"][0]["question_text"],
            "What is Python?"
        )
        self.assertEqual(
            data["rounds"][0]["questions"][0]["answers"][0]["answer_status"],
            "Correct"
        )
        self.assertEqual(data["skills"][0]["skill_name"], "Python")
        self.assertEqual(
            data["resources"][0]["resource_name"],
            "Python Documentation"
        )


if __name__ == "__main__":
    unittest.main()
