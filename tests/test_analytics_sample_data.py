import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class AnalyticsSampleDataTests(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        with self.client.session_transaction() as session:
            session["user_id"] = 2
            session["role"] = "coordinator"

    def tearDown(self):
        self.app_context.pop()

    def test_advanced_analytics_calculates_sample_data(self):

        with ExitStack() as stack:
            question_query = stack.enter_context(
                patch("routes.analytics.InterviewQuestion.query")
            )
            skill_query = stack.enter_context(
                patch("routes.analytics.InterviewSkill.query")
            )
            round_query = stack.enter_context(
                patch("routes.analytics.InterviewRound.query")
            )
            experience_query = stack.enter_context(
                patch("routes.analytics.InterviewExperience.query")
            )
            student_skill_query = stack.enter_context(
                patch("routes.analytics.StudentSkill.query")
            )
            grievance_query = stack.enter_context(
                patch("routes.analytics.Grievance.query")
            )
            student_query = stack.enter_context(
                patch("routes.analytics.Student.query")
            )

            question_query.all.return_value = [
                SimpleNamespace(question_text="What is Python?"),
                SimpleNamespace(question_text="what is python?"),
                SimpleNamespace(question_text="Explain SQL"),
            ]
            question_query.count.return_value = 3

            skill_query.all.return_value = [
                SimpleNamespace(skill_name="python"),
                SimpleNamespace(skill_name="Python"),
                SimpleNamespace(skill_name="sql"),
            ]
            skill_query.count.return_value = 3

            round_query.all.return_value = [
                SimpleNamespace(round_type="Technical"),
                SimpleNamespace(round_type="HR"),
                SimpleNamespace(round_type="Technical"),
            ]
            round_query.count.return_value = 3

            experience_query.all.return_value = [
                SimpleNamespace(overall_difficulty="Easy"),
                SimpleNamespace(overall_difficulty="Medium"),
                SimpleNamespace(overall_difficulty="Hard"),
            ]
            experience_query.count.return_value = 3

            student_skill_query.all.return_value = [
                SimpleNamespace(
                    proficiency="Beginner",
                    skill=SimpleNamespace(name="Python"),
                ),
                SimpleNamespace(
                    proficiency="Intermediate",
                    skill=SimpleNamespace(name="Python"),
                ),
                SimpleNamespace(
                    proficiency="Advanced",
                    skill=SimpleNamespace(name="SQL"),
                ),
            ]
            student_skill_query.count.return_value = 3

            grievance_query.all.return_value = [
                SimpleNamespace(
                    category=SimpleNamespace(name="Hostel"),
                    priority="High",
                    status="Submitted",
                    location="Block A",
                    assigned_to=5,
                ),
                SimpleNamespace(
                    category=SimpleNamespace(name="Hostel"),
                    priority="Medium",
                    status="Resolved",
                    location="Block A",
                    assigned_to=None,
                ),
                SimpleNamespace(
                    category=SimpleNamespace(name="Transport"),
                    priority="Low",
                    status="Submitted",
                    location=None,
                    assigned_to=None,
                ),
            ]
            grievance_query.count.return_value = 3

            student_query.all.return_value = [
                SimpleNamespace(cgpa=8.0),
                SimpleNamespace(cgpa=6.0),
                SimpleNamespace(cgpa=None),
            ]

            response = self.client.get("/api/analytics/advanced")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        interview = data["interview"]
        self.assertEqual(interview["total_experiences"], 3)
        self.assertEqual(interview["total_rounds"], 3)
        self.assertEqual(interview["total_questions"], 3)
        self.assertEqual(interview["total_interview_skills"], 3)

        self.assertEqual(
            interview["frequently_asked_questions"][0],
            {"question": "what is python?", "times_mentioned": 2},
        )
        self.assertEqual(
            interview["frequently_required_skills"][0],
            {"skill": "Python", "times_mentioned": 2},
        )
        self.assertEqual(
            interview["round_type_distribution"],
            {"Technical": 2, "HR": 1},
        )
        self.assertEqual(
            interview["difficulty_distribution"],
            {"Easy": 1, "Medium": 1, "Hard": 1},
        )

        student_skills = data["student_skills"]
        self.assertEqual(student_skills["total_student_skills"], 3)
        self.assertEqual(
            student_skills["proficiency_distribution"],
            {"Beginner": 1, "Intermediate": 1, "Advanced": 1},
        )
        self.assertEqual(
            student_skills["skill_distribution"],
            {"Python": 2, "SQL": 1},
        )

        grievances = data["grievances"]
        self.assertEqual(grievances["total_grievances"], 3)
        self.assertEqual(
            grievances["category_distribution"],
            {"Hostel": 2, "Transport": 1},
        )
        self.assertEqual(
            grievances["priority_distribution"],
            {"High": 1, "Medium": 1, "Low": 1},
        )
        self.assertEqual(
            grievances["status_distribution"],
            {"Submitted": 2, "Resolved": 1},
        )
        self.assertEqual(
            grievances["location_distribution"],
            {"Block A": 2, "Not specified": 1},
        )
        self.assertEqual(grievances["assigned_count"], 1)
        self.assertEqual(grievances["unassigned_count"], 2)

        readiness = data["placement_readiness"]
        self.assertEqual(readiness["students_with_cgpa"], 2)
        self.assertEqual(readiness["average_cgpa"], 7.0)
        self.assertEqual(
            readiness["observed_cgpa_group_distribution"],
            {"Higher CGPA group": 1, "Other CGPA group": 1},
        )


if __name__ == "__main__":
    unittest.main()
