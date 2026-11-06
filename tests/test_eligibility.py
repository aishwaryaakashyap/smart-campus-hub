import unittest
from types import SimpleNamespace

from services.eligibility import check_eligibility


class EligibilityTests(unittest.TestCase):

    def make_student(self, cgpa=8.0, branch="CSE", semester=6):
        return SimpleNamespace(
            cgpa=cgpa,
            branch=branch,
            semester=semester,
        )

    def make_drive(
        self,
        min_cgpa=None,
        eligible_branches=None,
        eligible_semester=None,
    ):
        return SimpleNamespace(
            min_cgpa=min_cgpa,
            eligible_branches=eligible_branches,
            eligible_semester=eligible_semester,
        )

    def test_student_is_eligible_when_no_requirements_exist(self):
        student = self.make_student()
        drive = self.make_drive()

        eligible, reasons = check_eligibility(student, drive)

        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_student_meets_minimum_cgpa(self):
        student = self.make_student(cgpa=8.5)
        drive = self.make_drive(min_cgpa=7.5)

        eligible, reasons = check_eligibility(student, drive)

        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_student_fails_minimum_cgpa(self):
        student = self.make_student(cgpa=6.0)
        drive = self.make_drive(min_cgpa=7.5)

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertEqual(len(reasons), 1)
        self.assertIn("CGPA requirement not met", reasons[0])

    def test_student_with_missing_cgpa_is_ineligible(self):
        student = self.make_student(cgpa=None)
        drive = self.make_drive(min_cgpa=7.0)

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertIn("CGPA requirement not met", reasons[0])

    def test_branch_matching_is_case_insensitive(self):
        student = self.make_student(branch="cse")
        drive = self.make_drive(eligible_branches="CSE, ISE, ECE")

        eligible, reasons = check_eligibility(student, drive)

        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_student_with_unlisted_branch_is_ineligible(self):
        student = self.make_student(branch="MECH")
        drive = self.make_drive(eligible_branches="CSE, ISE, ECE")

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertIn("Branch not eligible", reasons[0])

    def test_student_with_missing_branch_is_ineligible_when_restricted(self):
        student = self.make_student(branch=None)
        drive = self.make_drive(eligible_branches="CSE, ISE")

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertIn("Branch not eligible", reasons[0])

    def test_student_meets_semester_requirement(self):
        student = self.make_student(semester=6)
        drive = self.make_drive(eligible_semester=6)

        eligible, reasons = check_eligibility(student, drive)

        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_student_fails_semester_requirement(self):
        student = self.make_student(semester=4)
        drive = self.make_drive(eligible_semester=6)

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertIn("Semester requirement not met", reasons[0])

    def test_all_failed_requirements_are_reported(self):
        student = self.make_student(
            cgpa=5.0,
            branch="MECH",
            semester=4,
        )
        drive = self.make_drive(
            min_cgpa=7.0,
            eligible_branches="CSE, ISE",
            eligible_semester=6,
        )

        eligible, reasons = check_eligibility(student, drive)

        self.assertFalse(eligible)
        self.assertEqual(len(reasons), 3)
        self.assertIn("CGPA requirement not met", reasons[0])
        self.assertIn("Branch not eligible", reasons[1])
        self.assertIn("Semester requirement not met", reasons[2])


if __name__ == "__main__":
    unittest.main()
