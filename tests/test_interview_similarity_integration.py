
import unittest

from flask import Flask

from extensions import db
from models import (
    Company,
    InterviewExperience,
    InterviewQuestion,
    InterviewRound,
    Student,
    User,
)
from routes.interview_intelligence import intelligence_bp


class InterviewSimilarityIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            TESTING=True,
            SECRET_KEY="integration-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            INTERVIEW_SIMILARITY_THRESHOLD=0.30,
        )

        db.init_app(cls.app)
        cls.app.register_blueprint(
            intelligence_bp,
            url_prefix="/api/intelligence",
        )

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()
        self.client = self.app.test_client()

        self.user = User(
            name="Integration Student",
            email="integration.student@example.com",
            password_hash="test-password",
            role="student",
        )
        db.session.add(self.user)
        db.session.flush()

        self.student = Student(
            user_id=self.user.id,
            register_number="TEST001",
        )
        db.session.add(self.student)

        self.company = Company(name="Integration Test Company")
        db.session.add(self.company)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def set_session(self, user_id=None, role="student"):
        with self.client.session_transaction() as session:
            session["user_id"] = (
                self.user.id if user_id is None else user_id
            )
            session["role"] = role

    def add_experience_with_questions(self, company, questions):
        experience = InterviewExperience(
            student_id=self.student.id,
            company_id=company.id,
            selection_status="Selected",
            overall_difficulty="Medium",
        )
        db.session.add(experience)
        db.session.flush()

        interview_round = InterviewRound(
            experience_id=experience.id,
            round_number=1,
            round_type="Technical",
        )
        db.session.add(interview_round)
        db.session.flush()

        records = [
            InterviewQuestion(
                round_id=interview_round.id,
                question_text=question,
            )
            for question in questions
        ]

        db.session.add_all(records)
        db.session.commit()

        return records

    def test_rejects_unauthenticated_request(self):
        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_non_student_user(self):
        self.set_session(role="coordinator")

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 403)

    def test_rejects_missing_student_profile(self):
        self.set_session(user_id=99999)

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn(
            "Student profile not found",
            response.get_json()["error"],
        )

    def test_rejects_invalid_company_id(self):
        self.set_session()

        response = self.client.get(
            "/api/intelligence/company/99999"
        )

        self.assertEqual(response.status_code, 404)

    def test_company_without_experiences_returns_empty_similarity_list(self):
        self.set_session()

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["potentially_similar_questions"],
            [],
        )

    def test_company_with_experience_but_no_questions_returns_empty_list(self):
        self.set_session()

        experience = InterviewExperience(
            student_id=self.student.id,
            company_id=self.company.id,
            selection_status="Selected",
            overall_difficulty="Medium",
        )
        db.session.add(experience)
        db.session.commit()

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["potentially_similar_questions"],
            [],
        )

    def test_finds_similar_questions_from_database(self):
        self.set_session()

        records = self.add_experience_with_questions(
            self.company,
            [
                "Explain normalization in DBMS.",
                "What is database normalization?",
            ],
        )

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 200)

        matches = response.get_json()["potentially_similar_questions"]

        self.assertEqual(len(matches), 1)

        match = matches[0]

        self.assertEqual(match["question_id_1"], records[0].id)
        self.assertEqual(match["question_id_2"], records[1].id)
        self.assertEqual(match["question_1"], records[0].question_text)
        self.assertEqual(match["question_2"], records[1].question_text)
        self.assertGreater(match["similarity"], 0)
        self.assertLessEqual(match["similarity"], 1)
        self.assertEqual(match["label"], "Potentially Similar")

    def test_unrelated_questions_are_not_reported(self):
        self.set_session()

        self.add_experience_with_questions(
            self.company,
            [
                "Explain database normalization.",
                "Describe the process of photosynthesis.",
            ],
        )

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["potentially_similar_questions"],
            [],
        )

    def test_questions_from_another_company_are_not_compared(self):
        self.set_session()

        self.add_experience_with_questions(
            self.company,
            [
                "Explain normalization in DBMS.",
                "What is database normalization?",
            ],
        )

        another_company = Company(name="Another Company")
        db.session.add(another_company)
        db.session.commit()

        self.add_experience_with_questions(
            another_company,
            [
                "Explain normalization in DBMS.",
                "What is database normalization?",
            ],
        )

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        matches = response.get_json()["potentially_similar_questions"]

        self.assertEqual(len(matches), 1)

        other_company_ids = {
            question.id
            for question in InterviewQuestion.query
            .join(InterviewRound)
            .join(InterviewExperience)
            .filter(
                InterviewExperience.company_id == another_company.id
            )
            .all()
        }

        self.assertNotIn(matches[0]["question_id_1"], other_company_ids)
        self.assertNotIn(matches[0]["question_id_2"], other_company_ids)

    def test_invalid_similarity_threshold_is_rejected(self):
        self.set_session()

        for threshold in ("abc", "-0.1", "1.1"):
            response = self.client.get(
                f"/api/intelligence/company/{self.company.id}"
                f"?similarity_threshold={threshold}"
            )

            self.assertEqual(response.status_code, 400)

    def test_zero_threshold_does_not_report_zero_similarity(self):
        self.set_session()

        self.add_experience_with_questions(
            self.company,
            [
                "Explain database normalization.",
                "Describe the process of photosynthesis.",
            ],
        )

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
            "?similarity_threshold=0"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["potentially_similar_questions"],
            [],
        )

    def test_threshold_one_reports_identical_questions(self):
        self.set_session()

        self.add_experience_with_questions(
            self.company,
            [
                "What is Python programming?",
                "What is Python programming?",
            ],
        )

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
            "?similarity_threshold=1"
        )

        self.assertEqual(response.status_code, 200)

        matches = response.get_json()["potentially_similar_questions"]

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["similarity"], 1.0)

    def test_similarity_analysis_does_not_modify_interview_records(self):
        self.set_session()

        records = self.add_experience_with_questions(
            self.company,
            [
                "Explain normalization in DBMS.",
                "What is database normalization?",
            ],
        )

        before = [
            (record.id, record.round_id, record.question_text)
            for record in InterviewQuestion.query.order_by(
                InterviewQuestion.id
            ).all()
        ]

        response = self.client.get(
            f"/api/intelligence/company/{self.company.id}"
        )

        self.assertEqual(response.status_code, 200)

        after = [
            (record.id, record.round_id, record.question_text)
            for record in InterviewQuestion.query.order_by(
                InterviewQuestion.id
            ).all()
        ]

        self.assertEqual(before, after)
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
