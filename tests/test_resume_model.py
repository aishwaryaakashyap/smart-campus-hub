import unittest

from models import Resume


class ResumeModelTests(unittest.TestCase):

    def test_uses_resumes_table(self):
        self.assertEqual(Resume.__tablename__, "resumes")

    def test_student_id_is_required_and_unique(self):
        column = Resume.__table__.c.student_id

        self.assertFalse(column.nullable)
        self.assertTrue(column.unique)

    def test_student_id_references_students_table(self):
        column = Resume.__table__.c.student_id
        foreign_key_targets = {
            foreign_key.target_fullname
            for foreign_key in column.foreign_keys
        }

        self.assertIn("students.id", foreign_key_targets)

    def test_stored_filename_is_unique(self):
        column = Resume.__table__.c.stored_filename

        self.assertFalse(column.nullable)
        self.assertTrue(column.unique)

    def test_resume_content_fields_are_required(self):
        self.assertFalse(Resume.__table__.c.original_filename.nullable)
        self.assertFalse(Resume.__table__.c.extracted_text.nullable)

    def test_upload_timestamp_has_default(self):
        column = Resume.__table__.c.uploaded_at

        self.assertFalse(column.nullable)
        self.assertIsNotNone(column.default)


if __name__ == "__main__":
    unittest.main()
