import unittest
from datetime import datetime
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from models import Resume, Skill


class ResumeRouteTests(unittest.TestCase):

    def setUp(self):
        self.previous_testing = app.config.get("TESTING", False)
        self.previous_csrf = app.config.get("WTF_CSRF_ENABLED", True)
        self.previous_upload_folder = app.config.get("RESUME_UPLOAD_FOLDER")

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        self.temp_dir = TemporaryDirectory()
        app.config["RESUME_UPLOAD_FOLDER"] = self.temp_dir.name

        self.context = app.app_context()
        self.context.push()

        self.addCleanup(self.context.pop)
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(
            app.config.__setitem__, "RESUME_UPLOAD_FOLDER",
            self.previous_upload_folder
        )
        self.addCleanup(
            app.config.__setitem__, "WTF_CSRF_ENABLED",
            self.previous_csrf
        )
        self.addCleanup(
            app.config.__setitem__, "TESTING",
            self.previous_testing
        )

        self.client = app.test_client()

    def login(self, role="student", user_id=10):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def student_access(self):
        return patch(
            "routes.resume.require_student",
            return_value=(SimpleNamespace(id=7), None)
        )

    def test_rejects_unauthenticated_resume_request(self):
        response = self.client.get("/api/resumes/")
        self.assertEqual(response.status_code, 401)

    def test_rejects_non_student_role(self):
        self.login(role="coordinator")
        response = self.client.get("/api/resumes/")
        self.assertEqual(response.status_code, 403)

    def test_rejects_student_without_profile(self):
        self.login()

        with patch("routes.resume.Student.query") as query:
            query.filter_by.return_value.first.return_value = None
            response = self.client.get("/api/resumes/")

        self.assertEqual(response.status_code, 404)

    def test_rejects_non_pdf_filename(self):
        with self.student_access():
            response = self.client.post(
                "/api/resumes/",
                data={"resume": (BytesIO(b"document"), "resume.txt")},
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(list(Path(self.temp_dir.name).iterdir()))

    def test_rejects_invalid_pdf_signature(self):
        with self.student_access():
            response = self.client.post(
                "/api/resumes/",
                data={"resume": (BytesIO(b"not a PDF"), "resume.pdf")},
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(list(Path(self.temp_dir.name).iterdir()))

    def test_uploads_pdf_and_saves_private_file(self):
        with self.student_access(), \
             patch("routes.resume.Resume.query") as resume_query, \
             patch("routes.resume.Skill.query") as skill_query, \
             patch("routes.resume.extract_pdf_text",
                   return_value="Python and SQL developer") as extract, \
             patch("routes.resume.extract_resume_skills",
                   return_value=["Python", "SQL"]), \
             patch("routes.resume.db.session.add") as add, \
             patch("routes.resume.db.session.commit") as commit:

            resume_query.filter_by.return_value.first.return_value = None
            skill_query.all.return_value = []

            response = self.client.post(
                "/api/resumes/",
                data={
                    "resume": (
                        BytesIO(b"%PDF-1.7 test document"),
                        "my_resume.pdf"
                    )
                },
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["message"], "Resume uploaded successfully.")
        self.assertEqual(
            data["resume"]["extracted_skills"],
            ["Python", "SQL"]
        )
        self.assertEqual(data["resume"]["original_filename"], "my_resume.pdf")

        saved_files = list(Path(self.temp_dir.name).glob("*.pdf"))
        self.assertEqual(len(saved_files), 1)
        self.assertEqual(
            saved_files[0].read_bytes(),
            b"%PDF-1.7 test document"
        )

        add.assert_called_once()
        commit.assert_called_once()
        extract.assert_called_once()

    def test_replaces_existing_resume_and_removes_old_file(self):
        old_file = Path(self.temp_dir.name) / "old_resume.pdf"
        old_file.write_bytes(b"%PDF-old")

        existing = SimpleNamespace(
            id=22,
            student_id=7,
            original_filename="old.pdf",
            stored_filename="old_resume.pdf",
            extracted_text="Old resume",
            uploaded_at=datetime(2026, 1, 1)
        )

        with self.student_access(), \
             patch("routes.resume.Resume.query") as resume_query, \
             patch("routes.resume.Skill.query") as skill_query, \
             patch("routes.resume.extract_pdf_text",
                   return_value="New Python resume"), \
             patch("routes.resume.extract_resume_skills",
                   return_value=["Python"]), \
             patch("routes.resume.db.session.commit") as commit:

            resume_query.filter_by.return_value.first.return_value = existing
            skill_query.all.return_value = []

            response = self.client.post(
                "/api/resumes/",
                data={
                    "resume": (
                        BytesIO(b"%PDF-1.7 new document"),
                        "new_resume.pdf"
                    )
                },
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["message"],
            "Resume replaced successfully."
        )
        self.assertFalse(old_file.exists())

        new_file = Path(self.temp_dir.name) / existing.stored_filename
        self.assertTrue(new_file.exists())
        self.assertEqual(new_file.read_bytes(), b"%PDF-1.7 new document")
        commit.assert_called_once()

    def test_returns_resume_metadata(self):
        resume = SimpleNamespace(
            id=12,
            original_filename="resume.pdf",
            stored_filename="private.pdf",
            extracted_text="Python developer",
            uploaded_at=datetime(2026, 5, 1)
        )

        with self.student_access(), \
             patch("routes.resume.Resume.query") as resume_query, \
             patch("routes.resume.Skill.query") as skill_query, \
             patch("routes.resume.extract_resume_skills",
                   return_value=["Python"]):

            resume_query.filter_by.return_value.first.return_value = resume
            skill_query.all.return_value = []

            response = self.client.get("/api/resumes/")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()["resume"]
        self.assertEqual(result["id"], 12)
        self.assertEqual(result["original_filename"], "resume.pdf")
        self.assertEqual(result["extracted_skills"], ["Python"])
        self.assertNotIn("stored_filename", result)
        self.assertNotIn("extracted_text", result)

    def test_matches_resume_against_placement_drive(self):
        resume = SimpleNamespace(
            id=12,
            extracted_text="Python and SQL developer"
        )
        company = SimpleNamespace(name="Google")
        drive = SimpleNamespace(
            id=4,
            job_role="Python Developer",
            job_description="Python, SQL and AWS required",
            company=company
        )

        expected = {
            "resume_skills": ["Python", "SQL"],
            "required_skills": ["Python", "SQL", "AWS"],
            "matched_skills": ["Python", "SQL"],
            "missing_skills": ["AWS"],
            "total_required_skills": 3,
            "match_percentage": 66.67,
            "learning_priorities": [],
            "method": "Rule-based matching",
            "match_note": "Skill coverage only."
        }

        with self.student_access(), \
             patch("routes.resume.Resume.query") as resume_query, \
             patch("routes.resume.db.session.get", return_value=drive), \
             patch("routes.resume.Skill.query") as skill_query, \
             patch("routes.resume.analyze_resume_job_match",
                   return_value=expected) as matcher:

            resume_query.filter_by.return_value.first.return_value = resume
            skill_query.all.return_value = []

            response = self.client.get("/api/resumes/match/4")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()

        self.assertEqual(result["company_name"], "Google")
        self.assertEqual(result["job_role"], "Python Developer")
        self.assertEqual(result["match_percentage"], 66.67)
        matcher.assert_called_once()


    def test_rejects_missing_resume_upload(self):
        with self.student_access():
            response = self.client.post(
                "/api/resumes/",
                data={},
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(list(Path(self.temp_dir.name).iterdir()))

    def test_rejects_resume_larger_than_configured_limit(self):
        previous_limit = app.config.get("RESUME_MAX_BYTES")
        app.config["RESUME_MAX_BYTES"] = 8

        try:
            with self.student_access():
                response = self.client.post(
                    "/api/resumes/",
                    data={
                        "resume": (
                            BytesIO(b"%PDF-1.7 this file is too large"),
                            "large_resume.pdf"
                        )
                    },
                    content_type="multipart/form-data"
                )
        finally:
            if previous_limit is None:
                app.config.pop("RESUME_MAX_BYTES", None)
            else:
                app.config["RESUME_MAX_BYTES"] = previous_limit

        self.assertEqual(response.status_code, 413)
        self.assertFalse(list(Path(self.temp_dir.name).iterdir()))

    def test_returns_404_when_student_has_no_resume(self):
        with self.student_access(), patch(
            "routes.resume.Resume.query"
        ) as resume_query:
            resume_query.filter_by.return_value.first.return_value = None

            response = self.client.get("/api/resumes/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "No resume has been uploaded yet."
        )

    def test_job_match_returns_404_when_resume_is_missing(self):
        with self.student_access(), patch(
            "routes.resume.Resume.query"
        ) as resume_query, patch(
            "routes.resume.db.session.get"
        ) as get_record:
            resume_query.filter_by.return_value.first.return_value = None

            response = self.client.get("/api/resumes/match/4")

        self.assertEqual(response.status_code, 404)
        get_record.assert_not_called()

    def test_job_match_returns_404_for_unknown_drive(self):
        resume = SimpleNamespace(
            id=12,
            extracted_text="Python developer"
        )

        with self.student_access(), patch(
            "routes.resume.Resume.query"
        ) as resume_query, patch(
            "routes.resume.db.session.get",
            return_value=None
        ) as get_record:
            resume_query.filter_by.return_value.first.return_value = resume

            response = self.client.get("/api/resumes/match/999")

        self.assertEqual(response.status_code, 404)
        get_record.assert_called_once()

    def test_removes_new_file_when_database_save_fails(self):
        with self.student_access(), patch(
            "routes.resume.Resume.query"
        ) as resume_query, patch(
            "routes.resume.extract_pdf_text",
            return_value="Python developer"
        ), patch(
            "routes.resume.extract_resume_skills",
            return_value=["Python"]
        ), patch(
            "routes.resume.db.session.add"
        ) as add, patch(
            "routes.resume.db.session.commit",
            side_effect=RuntimeError("database error")
        ), patch(
            "routes.resume.db.session.rollback"
        ) as rollback:

            resume_query.filter_by.return_value.first.return_value = None

            response = self.client.post(
                "/api/resumes/",
                data={
                    "resume": (
                        BytesIO(b"%PDF-1.7 temporary resume"),
                        "temporary.pdf"
                    )
                },
                content_type="multipart/form-data"
            )

        self.assertEqual(response.status_code, 500)
        add.assert_called_once()
        rollback.assert_called_once()
        self.assertEqual(list(Path(self.temp_dir.name).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
