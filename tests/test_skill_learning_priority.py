
import unittest

from services.skill_gap import analyze_skill_gap


class SkillLearningPriorityTests(unittest.TestCase):

    def test_required_skill_gets_high_priority(self):
        result = analyze_skill_gap(
            "Python is required for this job.",
            [],
            [{"name": "Python"}],
        )

        self.assertEqual(
            result["learning_priorities"][0]["priority"],
            "High",
        )

    def test_preferred_skill_gets_low_priority(self):
        result = analyze_skill_gap(
            "Python is preferred for this job.",
            [],
            [{"name": "Python"}],
        )

        self.assertEqual(
            result["learning_priorities"][0]["priority"],
            "Low",
        )

    def test_skill_without_priority_wording_gets_medium_priority(self):
        result = analyze_skill_gap(
            "Python knowledge is useful for this job.",
            [],
            [{"name": "Python"}],
        )

        self.assertEqual(
            result["learning_priorities"][0]["priority"],
            "Medium",
        )

    def test_matched_skills_are_not_in_learning_priorities(self):
        result = analyze_skill_gap(
            "Python is required and SQL is preferred.",
            [{"skill_name": "Python"}],
            [{"name": "Python"}, {"name": "SQL"}],
        )

        self.assertEqual(
            [item["skill_name"] for item in result["learning_priorities"]],
            ["SQL"],
        )

    def test_nearby_skills_get_their_own_priorities(self):
        result = analyze_skill_gap(
            "Python is required, but SQL is preferred.",
            [],
            [{"name": "Python"}, {"name": "SQL"}],
        )

        priorities = {
            item["skill_name"]: item["priority"]
            for item in result["learning_priorities"]
        }

        self.assertEqual(priorities["Python"], "High")
        self.assertEqual(priorities["SQL"], "Low")


if __name__ == "__main__":
    unittest.main()
