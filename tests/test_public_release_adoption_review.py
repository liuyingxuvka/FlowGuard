import unittest

from flowguard.review import review_scenarios

from examples.public_release_adoption.model import scenarios


class PublicReleaseAdoptionReviewTests(unittest.TestCase):
    def test_public_release_adoption_review_matches_expected_outcomes(self):
        report = review_scenarios(scenarios())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(2, report.total_scenarios)
        self.assertEqual(1, report.passed)
        self.assertEqual(1, report.expected_violations_observed)

        statuses = {result.scenario_name: result.status for result in report.results}
        self.assertEqual(
            "expected_violation_observed",
            statuses["PRA01_v0_1_0_fresh_user_adoption_finds_install_gap"],
        )
        self.assertEqual(
            "pass",
            statuses["PRA02_v0_1_1_fresh_user_adoption_ready"],
        )


if __name__ == "__main__":
    unittest.main()
