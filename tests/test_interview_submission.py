import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class InterviewSubmissionTests(unittest.TestCase):

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

    def set_session(self, user_id=10, role="student"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def valid_payload(self, selection_status="Selected"):
        return {
            "company_id": 5,
            "job_role": "Python Developer",
            "year": 2026,
            "selection_status": selection_status,
            "overall_difficulty": "Medium",
            "preparation_summary": "Practised Python, DBMS and coding.",
            "selection_factors": "Strong technical preparation.",
            "rounds": [
                {
                    "round_number": 1,
                    "round_type": "Coding",
                    "mode": "Online",
                    "duration_minutes": 45,
                    "difficulty": "Medium",
                    "remarks": "Timed coding test.",
                    "questions": [
                        {
                            "question_text": "Explain Python lists.",
                            "topic": "Python",
                            "difficulty": "Medium",
                            "student_answer": "Lists are mutable collections.",
                            "answer_status": "Correct",
                            "reference_answer": "A list is an ordered, mutable collection."
                        }
                    ]
                }
            ],
            "skills": [
                {
                    "skill_name": "Python",
                    "importance_rating": 5
                }
            ],
            "resources": [
                {
                    "resource_type": "YouTube",
                    "resource_name": "Python Tutorial",
                    "url": "https://example.com/python",
                    "description": "Python preparation tutorial."
                }
            ]
        }

    def test_student_can_submit_complete_selected_experience(self):
        self.set_session()

        experience = SimpleNamespace(id=100)
        interview_round = SimpleNamespace(id=200)
        question = SimpleNamespace(id=300)

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query, patch(
            "routes.interview.InterviewExperience",
            return_value=experience
        ) as experience_model, patch(
            "routes.interview.InterviewRound",
            return_value=interview_round
        ) as round_model, patch(
            "routes.interview.InterviewQuestion",
            return_value=question
        ) as question_model, patch(
            "routes.interview.StudentAnswer"
        ) as answer_model, patch(
            "routes.interview.InterviewSkill"
        ) as skill_model, patch(
            "routes.interview.PreparationResource"
        ) as resource_model, patch(
            "routes.interview.db.session.add"
        ) as add, patch(
            "routes.interview.db.session.flush"
        ) as flush, patch(
            "routes.interview.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )
            company_query.get.return_value = SimpleNamespace(id=5)

            response = self.client.post(
                "/api/interviews/",
                json=self.valid_payload("Selected")
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["id"], 100)

        experience_model.assert_called_once_with(
            student_id=7,
            company_id=5,
            job_role="Python Developer",
            year=2026,
            selection_status="Selected",
            overall_difficulty="Medium",
            preparation_summary="Practised Python, DBMS and coding.",
            selection_factors="Strong technical preparation."
        )

        round_model.assert_called_once_with(
            experience_id=100,
            round_number=1,
            round_type="Coding",
            mode="Online",
            duration_minutes=45,
            difficulty="Medium",
            remarks="Timed coding test."
        )

        question_model.assert_called_once_with(
            round_id=200,
            question_text="Explain Python lists.",
            topic="Python",
            difficulty="Medium"
        )

        answer_model.assert_called_once_with(
            question_id=300,
            student_answer="Lists are mutable collections.",
            answer_status="Correct",
            reference_answer="A list is an ordered, mutable collection."
        )

        skill_model.assert_called_once_with(
            experience_id=100,
            skill_name="Python",
            importance_rating=5
        )

        resource_model.assert_called_once_with(
            experience_id=100,
            resource_type="YouTube",
            resource_name="Python Tutorial",
            url="https://example.com/python",
            description="Python preparation tutorial."
        )

        self.assertEqual(add.call_count, 6)
        self.assertEqual(flush.call_count, 3)
        commit.assert_called_once()

    def test_student_can_submit_not_selected_experience(self):
        self.set_session()

        experience = SimpleNamespace(id=101)

        payload = self.valid_payload("Not Selected")
        payload["rounds"] = []
        payload["skills"] = []
        payload["resources"] = []

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query, patch(
            "routes.interview.InterviewExperience",
            return_value=experience
        ) as experience_model, patch(
            "routes.interview.db.session.add"
        ) as add, patch(
            "routes.interview.db.session.flush"
        ), patch(
            "routes.interview.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )
            company_query.get.return_value = SimpleNamespace(id=5)

            response = self.client.post(
                "/api/interviews/",
                json=payload
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["id"], 101)
        self.assertEqual(
            experience_model.call_args.kwargs["selection_status"],
            "Not Selected"
        )
        add.assert_called_once_with(experience)
        commit.assert_called_once()

    def test_unauthenticated_student_cannot_submit_experience(self):
        with patch("routes.interview.Company.query") as company_query:
            response = self.client.post(
                "/api/interviews/",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 401)
        company_query.get.assert_not_called()

    def test_coordinator_cannot_submit_student_experience(self):
        self.set_session(role="coordinator")

        with patch("routes.interview.Company.query") as company_query:
            response = self.client.post(
                "/api/interviews/",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 403)
        company_query.get.assert_not_called()

    def test_student_without_profile_cannot_submit_experience(self):
        self.set_session()

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query:

            student_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                "/api/interviews/",
                json=self.valid_payload()
            )

        self.assertEqual(response.status_code, 404)
        company_query.get.assert_not_called()

    def test_rejects_invalid_json_structure(self):
        self.set_session()

        with patch(
            "routes.interview.Student.query"
        ) as student_query:
            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )

            response = self.client.post(
                "/api/interviews/",
                json=["not", "an", "object"]
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "A valid JSON object is required"
        )

    def test_rejects_non_list_rounds(self):
        self.set_session()

        payload = self.valid_payload()
        payload["rounds"] = {"round_type": "Coding"}

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )
            company_query.get.return_value = SimpleNamespace(id=5)

            response = self.client.post(
                "/api/interviews/",
                json=payload
            )

        self.assertEqual(response.status_code, 400)

    def test_rejects_non_object_round(self):
        self.set_session()

        payload = self.valid_payload()
        payload["rounds"] = ["Coding"]

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )
            company_query.get.return_value = SimpleNamespace(id=5)

            response = self.client.post(
                "/api/interviews/",
                json=payload
            )

        self.assertEqual(response.status_code, 400)


    def test_rejects_malformed_nested_data_before_database_writes(self):
        self.set_session()

        cases = []

        payload = self.valid_payload()
        payload["rounds"] = "not a list"
        cases.append(("rounds must be a list", payload))

        payload = self.valid_payload()
        payload["rounds"] = ["Coding"]
        cases.append(("round must be an object", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["questions"] = "not a list"
        cases.append(("questions must be a list", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["questions"] = ["invalid question"]
        cases.append(("question must be an object", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["questions"][0]["question_text"] = " "
        cases.append(("question text is required", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["round_type"] = "Unknown"
        cases.append(("invalid round type", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["difficulty"] = "Impossible"
        cases.append(("invalid round difficulty", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["questions"][0]["difficulty"] = "Impossible"
        cases.append(("invalid question difficulty", payload))

        payload = self.valid_payload()
        payload["rounds"][0]["questions"][0]["answer_status"] = "Unknown"
        cases.append(("invalid answer status", payload))

        payload = self.valid_payload()
        payload["skills"] = "not a list"
        cases.append(("skills must be a list", payload))

        payload = self.valid_payload()
        payload["skills"] = ["Python"]
        cases.append(("skill must be an object", payload))

        payload = self.valid_payload()
        payload["skills"][0]["skill_name"] = " "
        cases.append(("skill name is required", payload))

        payload = self.valid_payload()
        payload["resources"] = "not a list"
        cases.append(("resources must be a list", payload))

        payload = self.valid_payload()
        payload["resources"] = ["Tutorial"]
        cases.append(("resource must be an object", payload))

        payload = self.valid_payload()
        payload["resources"][0]["resource_name"] = " "
        cases.append(("resource name is required", payload))

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query, patch(
            "routes.interview.InterviewExperience"
        ) as experience_model, patch(
            "routes.interview.db.session.add"
        ) as add, patch(
            "routes.interview.db.session.flush"
        ) as flush, patch(
            "routes.interview.db.session.commit"
        ) as commit:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )
            company_query.get.return_value = SimpleNamespace(id=5)

            for label, payload in cases:
                with self.subTest(case=label):
                    response = self.client.post(
                        "/api/interviews/",
                        json=deepcopy(payload)
                    )
                    self.assertEqual(
                        response.status_code,
                        400,
                        msg=f"{label}: {response.get_json()}"
                    )

            experience_model.assert_not_called()
            add.assert_not_called()
            flush.assert_not_called()
            commit.assert_not_called()

    def test_rejects_invalid_company_id_before_database_lookup(self):
        self.set_session()

        payload = self.valid_payload()
        payload["company_id"] = True

        with patch(
            "routes.interview.Student.query"
        ) as student_query, patch(
            "routes.interview.Company.query"
        ) as company_query, patch(
            "routes.interview.db.session.add"
        ) as add:

            student_query.filter_by.return_value.first.return_value = (
                SimpleNamespace(id=7)
            )

            response = self.client.post(
                "/api/interviews/",
                json=payload
            )

        self.assertEqual(response.status_code, 400)
        company_query.get.assert_not_called()
        add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
