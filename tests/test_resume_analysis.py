import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from services.resume_analysis import (
    ResumeProcessingError,
    extract_pdf_text,
    extract_resume_skills,
    analyze_resume_job_match,
)


class ResumePdfExtractionTests(unittest.TestCase):

    def make_stream(self):
        return BytesIO(b"%PDF-1.7 test PDF bytes")

    def make_reader(self, page_texts, encrypted=False):
        pages = []

        for text in page_texts:
            page = MagicMock()
            page.extract_text.return_value = text
            pages.append(page)

        reader = MagicMock()
        reader.is_encrypted = encrypted
        reader.pages = pages
        return reader

    def test_extracts_and_normalizes_multiple_pages(self):
        stream = self.make_stream()
        reader = self.make_reader([
            "  Aishwarya   Kashyap  \nPython Developer ",
            " SQL   and   Flask experience ",
        ])

        with patch("services.resume_analysis.PdfReader", return_value=reader):
            result = extract_pdf_text(stream)

        self.assertEqual(
            result,
            "Aishwarya Kashyap\nPython Developer\nSQL and Flask experience",
        )
        self.assertEqual(stream.tell(), 0)

    def test_rejects_invalid_pdf_signature(self):
        with self.assertRaisesRegex(ResumeProcessingError, "not a valid PDF"):
            extract_pdf_text(BytesIO(b"not a PDF"))

    def test_rejects_encrypted_pdf(self):
        reader = self.make_reader(["Private text"], encrypted=True)

        with patch("services.resume_analysis.PdfReader", return_value=reader):
            with self.assertRaisesRegex(ResumeProcessingError, "Password-protected"):
                extract_pdf_text(self.make_stream())

    def test_rejects_pdf_without_pages(self):
        reader = self.make_reader([])

        with patch("services.resume_analysis.PdfReader", return_value=reader):
            with self.assertRaisesRegex(ResumeProcessingError, "does not contain"):
                extract_pdf_text(self.make_stream())

    def test_rejects_scanned_pdf_without_selectable_text(self):
        reader = self.make_reader([None, "   "])

        with patch("services.resume_analysis.PdfReader", return_value=reader):
            with self.assertRaisesRegex(ResumeProcessingError, "No selectable text"):
                extract_pdf_text(self.make_stream())

    def test_reports_page_extraction_errors(self):
        page = MagicMock()
        page.extract_text.side_effect = RuntimeError("parser error")

        reader = MagicMock()
        reader.is_encrypted = False
        reader.pages = [page]

        with patch("services.resume_analysis.PdfReader", return_value=reader):
            with self.assertRaisesRegex(ResumeProcessingError, "PDF page 1"):
                extract_pdf_text(self.make_stream())

    def test_reports_corrupted_pdf_errors(self):
        with patch(
            "services.resume_analysis.PdfReader",
            side_effect=RuntimeError("damaged PDF"),
        ):
            with self.assertRaisesRegex(ResumeProcessingError, "damaged or unsupported"):
                extract_pdf_text(self.make_stream())

    def test_rejects_missing_file_stream(self):
        with self.assertRaisesRegex(ResumeProcessingError, "readable PDF"):
            extract_pdf_text(None)


    def test_extracts_canonical_skills_case_insensitively(self):
        result = extract_resume_skills(
            "Experienced in PYTHON, sql and Flask development.",
            [
                {"name": "Python"},
                {"name": "SQL"},
                {"name": "Flask"},
                {"name": "Java"},
            ],
        )
        self.assertEqual(result, ["Python", "SQL", "Flask"])

    def test_extracts_existing_skill_catalogue_aliases(self):
        result = extract_resume_skills(
            "Used DBMS, DSA and REST API development.",
            [
                {"name": "Database Management"},
                {"name": "Data Structures"},
                {"name": "API Development"},
            ],
        )
        self.assertEqual(
            result,
            ["Database Management", "Data Structures", "API Development"],
        )

    def test_does_not_match_partial_skill_names(self):
        result = extract_resume_skills(
            "Built applications using JavaScript.",
            [{"name": "Java"}, {"name": "Python"}],
        )
        self.assertEqual(result, [])

    def test_deduplicates_skill_catalogue_entries(self):
        result = extract_resume_skills(
            "Python and SQL experience.",
            [
                {"name": "Python"},
                {"name": " python "},
                {"name": "SQL"},
                {"name": "SQL"},
            ],
        )
        self.assertEqual(result, ["Python", "SQL"])

    def test_ignores_invalid_catalogue_entries(self):
        result = extract_resume_skills(
            "Python developer.",
            [None, {}, {"name": ""}, {"name": "   "}, {"name": "Python"}],
        )
        self.assertEqual(result, ["Python"])

    def test_accepts_skill_model_like_objects(self):
        skill = MagicMock()
        skill.name = "SQL"

        result = extract_resume_skills("SQL developer.", [skill])
        self.assertEqual(result, ["SQL"])

    def test_rejects_blank_resume_text_for_skill_extraction(self):
        with self.assertRaisesRegex(
            ResumeProcessingError, "Resume text is required"
        ):
            extract_resume_skills("   ", [{"name": "Python"}])

    def test_rejects_invalid_skill_catalogue(self):
        with self.assertRaisesRegex(
            ResumeProcessingError, "catalogue must be a list"
        ):
            extract_resume_skills("Python developer.", None)


    def test_matches_resume_skills_against_job_requirements(self):
        result = analyze_resume_job_match(
            "Developed Python applications and worked with SQL.",
            "Python and SQL required. AWS is essential.",
            [
                {"name": "Python"},
                {"name": "SQL"},
                {"name": "AWS"},
                {"name": "Flask"},
            ],
        )

        self.assertEqual(result["resume_skills"], ["Python", "SQL"])
        self.assertEqual(result["required_skills"], ["Python", "SQL", "AWS"])
        self.assertEqual(result["matched_skills"], ["Python", "SQL"])
        self.assertEqual(result["missing_skills"], ["AWS"])
        self.assertEqual(result["match_percentage"], 66.67)
        self.assertEqual(
            result["learning_priorities"][0]["skill_name"], "AWS"
        )
        self.assertIn("not an ATS score", result["match_note"])

    def test_returns_zero_when_no_resume_skills_match_job(self):
        result = analyze_resume_job_match(
            "Created websites using JavaScript.",
            "Java and Python are required.",
            [{"name": "Java"}, {"name": "Python"}],
        )

        self.assertEqual(result["resume_skills"], [])
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["missing_skills"], ["Java", "Python"])
        self.assertEqual(result["match_percentage"], 0.0)

    def test_returns_none_percentage_when_job_has_no_catalogue_skills(self):
        result = analyze_resume_job_match(
            "Python developer with SQL experience.",
            "Good communication and teamwork.",
            [{"name": "Python"}, {"name": "SQL"}],
        )

        self.assertEqual(result["resume_skills"], ["Python", "SQL"])
        self.assertEqual(result["required_skills"], [])
        self.assertIsNone(result["match_percentage"])

    def test_supports_skill_model_like_objects(self):
        python_skill = MagicMock()
        python_skill.name = "Python"
        sql_skill = MagicMock()
        sql_skill.name = "SQL"

        result = analyze_resume_job_match(
            "Python developer.",
            "Python and SQL required.",
            [python_skill, sql_skill],
        )

        self.assertEqual(result["matched_skills"], ["Python"])
        self.assertEqual(result["missing_skills"], ["SQL"])
        self.assertEqual(result["match_percentage"], 50.0)

    def test_rejects_non_text_job_description(self):
        with self.assertRaisesRegex(
            ResumeProcessingError, "Job description must be text"
        ):
            analyze_resume_job_match(
                "Python developer.",
                {"description": "Python required"},
                [{"name": "Python"}],
            )

    def test_rejects_invalid_skill_catalogue_for_job_matching(self):
        with self.assertRaisesRegex(
            ResumeProcessingError, "catalogue must be a list"
        ):
            analyze_resume_job_match(
                "Python developer.",
                "Python required.",
                None,
            )


if __name__ == "__main__":
    unittest.main()
