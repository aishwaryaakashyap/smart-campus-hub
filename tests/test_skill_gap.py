import unittest

from services.skill_gap import analyze_skill_gap


class SkillGapServiceTests(unittest.TestCase):

    def test_identifies_matched_and_missing_skills(self):
        result = analyze_skill_gap(
            "We need Python and SQL skills.",
            [{"skill_name": "Python"}],
            [{"name": "Python"}, {"name": "SQL"}, {"name": "Java"}]
        )

        self.assertEqual(result["required_skills"], ["Python", "SQL"])
        self.assertEqual(result["matched_skills"], ["Python"])
        self.assertEqual(result["missing_skills"], ["SQL"])
        self.assertEqual(result["total_required_skills"], 2)
        self.assertEqual(result["match_percentage"], 50.0)

    def test_matching_is_case_insensitive(self):
        result = analyze_skill_gap(
            "PYTHON developer",
            [{"skill_name": "python"}],
            [{"name": "Python"}]
        )

        self.assertEqual(result["matched_skills"], ["Python"])
        self.assertEqual(result["match_percentage"], 100.0)

    def test_does_not_match_partial_skill_names(self):
        result = analyze_skill_gap(
            "Experience with JavaScript is required.",
            [],
            [{"name": "Java"}]
        )

        self.assertEqual(result["required_skills"], [])

    def test_returns_none_percentage_when_no_skills_are_required(self):
        result = analyze_skill_gap(
            "Good communication skills are helpful.",
            [],
            [{"name": "Python"}, {"name": "SQL"}]
        )

        self.assertEqual(result["total_required_skills"], 0)
        self.assertIsNone(result["match_percentage"])
        self.assertEqual(result["missing_skills"], [])

    def test_handles_empty_job_description(self):
        result = analyze_skill_gap(
            "",
            [{"skill_name": "Python"}],
            [{"name": "Python"}]
        )

        self.assertEqual(result["required_skills"], [])
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["missing_skills"], [])
        self.assertIsNone(result["match_percentage"])


if __name__ == "__main__":
    unittest.main()
