
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from routes.interview_intelligence import build_preparation_recommendations


class InterviewIntelligenceTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)

        app.config["TESTING"] = True

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

    def test_rejects_unauthenticated_request(self):
        response = self.client.get("/api/intelligence/company/1")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Not logged in")

    def test_rejects_non_student_role(self):
        self.set_session(role="coordinator")

        response = self.client.get("/api/intelligence/company/1")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["error"],
            "Only students can view interview intelligence",
        )

    def test_returns_404_for_unknown_company(self):
        self.set_session()

        with patch(
            "routes.interview_intelligence.Company.query"
        ) as company_query:
            company_query.get.return_value = None

            response = self.client.get("/api/intelligence/company/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Company not found")

    def test_handles_company_with_no_experiences(self):
        self.set_session()
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
        self.set_session()

        question = SimpleNamespace(question_text=" What is Python? ", topic=None)
        interview_round = SimpleNamespace(
            round_type="Technical",
            questions=[question],
        )
        skill = SimpleNamespace(skill_name="python", importance_rating=4)

        experience = SimpleNamespace(
            selection_status="Selected",
            overall_difficulty="Hard",
            rounds=[interview_round],
            skills=[skill],
            resources=[],
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
            "what is python?",
        )
        self.assertEqual(
            data["frequently_required_skills"][0]["skill"],
            "Python",
        )
        self.assertEqual(
            data["skill_priorities"][0]["average_importance_rating"],
            4.0,
        )

    def test_ignores_invalid_difficulty_and_skill_ratings_and_limits_resources(self):
        self.set_session()

        skills = [
            SimpleNamespace(skill_name="python", importance_rating=3),
            SimpleNamespace(skill_name="PYTHON", importance_rating=5),
            SimpleNamespace(skill_name="python", importance_rating=9),
            SimpleNamespace(skill_name="python", importance_rating=True),
            SimpleNamespace(skill_name="python", importance_rating=None),
        ]
        resources = [
            SimpleNamespace(
                resource_name=f"Resource {index}",
                resource_type="Article",
                url=f"https://example.com/{index}",
                description=None,
            )
            for index in range(12)
        ]
        experience = SimpleNamespace(
            selection_status="Not Selected",
            overall_difficulty="not-a-difficulty",
            rounds=[],
            skills=skills,
            resources=resources,
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
        self.assertIsNone(data["average_difficulty_score"])
        self.assertEqual(data["skill_priorities"][0]["skill"], "Python")
        self.assertEqual(
            data["skill_priorities"][0]["average_importance_rating"],
            4.0,
        )
        self.assertEqual(len(data["preparation_resources"]), 10)
        self.assertEqual(data["not_selected_count"], 1)

    def test_preparation_recommendation_difficulty_thresholds(self):
        moderate = build_preparation_recommendations(
            Counter(), [], Counter(), 1.75
        )
        high = build_preparation_recommendations(
            Counter(), [], Counter(), 2.5
        )
        fallback = build_preparation_recommendations(
            Counter(), [], Counter(), None
        )

        self.assertEqual(
            moderate[0]["title"], "Strengthen your fundamentals"
        )
        self.assertEqual(high[0]["title"], "Plan extra practice time")
        self.assertEqual(fallback[0]["category"], "General")


if __name__ == "__main__":
    unittest.main()
