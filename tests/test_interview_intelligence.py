import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class InterviewIntelligenceTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        app.config["TESTING"] = True

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()
        app.config["TESTING"] = self.previous_testing

    def test_returns_404_for_unknown_company(self):
        with patch(
            "routes.interview_intelligence.Company.query"
        ) as company_query:
            company_query.get.return_value = None

            response = self.client.get("/api/intelligence/company/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Company not found")

    def test_handles_company_with_no_experiences(self):
        company = SimpleNamespace(name="Test Company")

        with patch(
            "routes.interview_intelligence.Company.query"
        ) as company_query, patch(
            "routes.interview_intelligence.InterviewExperience.query"
        ) as experience_query:
            company_query.get.return_value = company
            experience_query.filter_by.return_value.all.return_value = []

            response = self.client.get("/api/intelligence/company/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["company_name"], "Test Company")
        self.assertEqual(response.get_json()["total_experiences"], 0)

    def test_summarizes_questions_skills_and_difficulty(self):
        question = SimpleNamespace(question_text=" What is Python? ")
        interview_round = SimpleNamespace(
            round_type="Technical",
            questions=[question]
        )
        skill = SimpleNamespace(skill_name="python")

        experience = SimpleNamespace(
            selection_status="Selected",
            overall_difficulty="Hard",
            rounds=[interview_round],
            skills=[skill]
        )
        company = SimpleNamespace(name="Test Company")

        with patch(
            "routes.interview_intelligence.Company.query"
        ) as company_query, patch(
            "routes.interview_intelligence.InterviewExperience.query"
        ) as experience_query:
            company_query.get.return_value = company
            experience_query.filter_by.return_value.all.return_value = [
                experience
            ]

            response = self.client.get("/api/intelligence/company/1")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["total_experiences"], 1)
        self.assertEqual(data["selected_count"], 1)
        self.assertEqual(data["not_selected_count"], 0)
        self.assertEqual(data["average_difficulty_score"], 3.0)
        self.assertEqual(data["round_type_distribution"]["Technical"], 1)
        self.assertEqual(
            data["frequently_asked_questions"][0]["question"],
            "what is python?"
        )
        self.assertEqual(
            data["frequently_required_skills"][0]["skill"],
            "Python"
        )


if __name__ == "__main__":
    unittest.main()
