import unittest
from unittest.mock import patch

from app import app


class AnalyticsIntegrationTests(unittest.TestCase):

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

    @patch("routes.analytics.Application.query")
    @patch("routes.analytics.PlacementDrive.query")
    @patch("routes.analytics.Company.query")
    @patch("routes.analytics.Student.query")
    def test_placement_analytics_handles_empty_data(
        self,
        student_query,
        company_query,
        drive_query,
        application_query,
    ):
        student_query.count.return_value = 0
        company_query.count.return_value = 0
        company_query.all.return_value = []
        drive_query.count.return_value = 0
        drive_query.filter_by.return_value.count.return_value = 0
        application_query.count.return_value = 0
        application_query.filter_by.return_value.count.return_value = 0

        response = self.client.get("/api/analytics/placement")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["total_students"], 0)
        self.assertEqual(data["total_companies"], 0)
        self.assertEqual(data["total_drives"], 0)
        self.assertEqual(data["total_applications"], 0)
        self.assertEqual(data["selected_count"], 0)
        self.assertEqual(data["selection_rate_percent"], 0)
        self.assertEqual(data["company_analytics"], [])
        self.assertIn("application_status_counts", data)

    @patch("routes.analytics.Student.query")
    @patch("routes.analytics.Grievance.query")
    @patch("routes.analytics.StudentSkill.query")
    @patch("routes.analytics.InterviewExperience.query")
    @patch("routes.analytics.InterviewRound.query")
    @patch("routes.analytics.InterviewSkill.query")
    @patch("routes.analytics.InterviewQuestion.query")
    def test_advanced_analytics_handles_empty_data(
        self,
        question_query,
        interview_skill_query,
        round_query,
        experience_query,
        student_skill_query,
        grievance_query,
        student_query,
    ):
        question_query.all.return_value = []
        question_query.count.return_value = 0

        interview_skill_query.all.return_value = []
        interview_skill_query.count.return_value = 0

        round_query.all.return_value = []
        round_query.count.return_value = 0

        experience_query.all.return_value = []
        experience_query.count.return_value = 0

        student_skill_query.all.return_value = []
        student_skill_query.count.return_value = 0

        grievance_query.all.return_value = []
        grievance_query.count.return_value = 0

        student_query.all.return_value = []

        response = self.client.get("/api/analytics/advanced")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["interview"]["total_experiences"], 0)
        self.assertEqual(data["interview"]["total_rounds"], 0)
        self.assertEqual(data["interview"]["total_questions"], 0)
        self.assertEqual(data["student_skills"]["total_student_skills"], 0)
        self.assertEqual(data["grievances"]["total_grievances"], 0)

        readiness = data["placement_readiness"]
        self.assertEqual(readiness["students_with_cgpa"], 0)
        self.assertIsNone(readiness["average_cgpa"])
        self.assertEqual(
            readiness["observed_cgpa_group_distribution"],
            {"Higher CGPA group": 0, "Other CGPA group": 0},
        )
        self.assertIn("not an ML prediction", readiness["note"])

    def test_coordinator_can_load_analytics_dashboard(self):
        response = self.client.get("/api/analytics/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Smart Campus Analytics Dashboard",
            response.data,
        )


    @patch("routes.analytics.Application.query")
    @patch("routes.analytics.PlacementDrive.query")
    @patch("routes.analytics.Company.query")
    @patch("routes.analytics.Student.query")
    def test_placement_analytics_calculates_selection_rate(
        self,
        student_query,
        company_query,
        drive_query,
        application_query,
    ):
        student_query.count.return_value = 3

        company = type("CompanyStub", (), {"id": 10, "name": "Acme"})()
        company_query.count.return_value = 1
        company_query.all.return_value = [company]

        drive = type("DriveStub", (), {"id": 20})()
        drive_query.count.return_value = 1
        drive_query.filter_by.return_value.count.return_value = 1
        drive_query.filter_by.return_value.all.return_value = [drive]

        selected = type("ApplicationStub", (), {"status": "Selected"})()
        applied = type("ApplicationStub", (), {"status": "Applied"})()

        application_query.count.return_value = 2

        def count_applications_by_status(**kwargs):
            query = type("QueryStub", (), {})()
            query.count = lambda: (
                1 if kwargs.get("status") == "Selected" else
                1 if kwargs.get("status") == "Applied" else 0
            )
            return query

        application_query.filter_by.side_effect = count_applications_by_status
        application_query.filter.return_value.all.return_value = [
            selected, applied
        ]

        response = self.client.get("/api/analytics/placement")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["total_students"], 3)
        self.assertEqual(data["total_companies"], 1)
        self.assertEqual(data["total_drives"], 1)
        self.assertEqual(data["total_applications"], 2)
        self.assertEqual(data["selected_count"], 1)
        self.assertEqual(data["selection_rate_percent"], 50.0)
        company_data = data["company_analytics"][0]
        self.assertEqual(company_data["company_name"], "Acme")
        self.assertEqual(company_data["application_count"], 2)
        self.assertEqual(company_data["selected_count"], 1)
        self.assertEqual(company_data["selection_rate_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
