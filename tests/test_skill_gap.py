import unittest

from services.skill_gap import analyze_skill_gap


class SkillGapAnalysisTests(unittest.TestCase):

    def setUp(self):
        self.available_skills = [
            {"name": "Python"},
            {"name": "Java"},
            {"name": "SQL"},
            {"name": "Machine Learning"},
            {"name": "C++"},
        ]

    def test_identifies_matched_and_missing_skills(self):
        result = analyze_skill_gap(
            "We need Python, Java and SQL knowledge.",
            [
                {"skill_name": "Python", "proficiency": "Advanced"},
                {"skill_name": "SQL", "proficiency": "Intermediate"},
            ],
            self.available_skills,
        )

        self.assertEqual(
            result["required_skills"],
            ["Python", "Java", "SQL"],
        )
        self.assertEqual(
            result["matched_skills"],
            ["Python", "SQL"],
        )
        self.assertEqual(
            result["missing_skills"],
            ["Java"],
        )
        self.assertEqual(result["total_required_skills"], 3)
        self.assertEqual(result["match_percentage"], 66.67)

    def test_skill_matching_is_case_insensitive(self):
        result = analyze_skill_gap(
            "PYTHON and sql experience required.",
            [{"skill_name": "python", "proficiency": "Advanced"}],
            self.available_skills,
        )

        self.assertEqual(result["matched_skills"], ["Python"])
        self.assertEqual(result["missing_skills"], ["SQL"])
        self.assertEqual(result["match_percentage"], 50.0)

    def test_does_not_match_partial_skill_names(self):
        result = analyze_skill_gap(
            "Experience with JavaScript is required.",
            [],
            [
                {"name": "Java"},
                {"name": "Python"},
            ],
        )

        self.assertEqual(result["required_skills"], [])
        self.assertEqual(result["missing_skills"], [])
        self.assertIsNone(result["match_percentage"])

    def test_handles_empty_job_description(self):
        result = analyze_skill_gap(
            "",
            [{"skill_name": "Python", "proficiency": "Advanced"}],
            self.available_skills,
        )

        self.assertEqual(result["required_skills"], [])
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["total_required_skills"], 0)
        self.assertIsNone(result["match_percentage"])

    def test_handles_none_job_description(self):
        result = analyze_skill_gap(
            None,
            [],
            self.available_skills,
        )

        self.assertEqual(result["required_skills"], [])
        self.assertIsNone(result["match_percentage"])

    def test_ignores_blank_available_skill_names(self):
        result = analyze_skill_gap(
            "Python developer required.",
            [],
            [
                {"name": ""},
                {"name": "   "},
                {"name": "Python"},
            ],
        )

        self.assertEqual(result["required_skills"], ["Python"])
        self.assertEqual(result["missing_skills"], ["Python"])

    def test_ignores_blank_student_skill_names(self):
        result = analyze_skill_gap(
            "Python and SQL required.",
            [
                {"skill_name": ""},
                {"skill_name": "   "},
            ],
            self.available_skills,
        )

        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(
            result["missing_skills"],
            ["Python", "SQL"],
        )
        self.assertEqual(result["match_percentage"], 0.0)

    def test_match_percentage_is_100_when_all_skills_match(self):
        result = analyze_skill_gap(
            "Python and SQL required.",
            [
                {"skill_name": "Python", "proficiency": "Advanced"},
                {"skill_name": "SQL", "proficiency": "Intermediate"},
            ],
            self.available_skills,
        )

        self.assertEqual(result["match_percentage"], 100.0)
        self.assertEqual(result["missing_skills"], [])

    def test_returns_matching_method(self):
        result = analyze_skill_gap(
            "Python required.",
            [],
            self.available_skills,
        )

        self.assertEqual(
            result["method"],
            "Rule-based matching against the existing skill catalog",
        )


    def test_returns_none_percentage_when_no_skills_are_required(self):
        result = analyze_skill_gap(
            "Good communication skills are helpful.",
            [],
            [{"name": "Python"}, {"name": "SQL"}],
        )

        self.assertEqual(result["total_required_skills"], 0)
        self.assertIsNone(result["match_percentage"])
        self.assertEqual(result["missing_skills"], [])

if __name__ == "__main__":
    unittest.main()

