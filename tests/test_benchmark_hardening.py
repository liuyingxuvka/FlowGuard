import subprocess
import sys
import unittest

from examples.problem_corpus.coverage_audit import review_benchmark_coverage
from examples.problem_corpus.conformance_seeds import review_conformance_seeds
from examples.problem_corpus.family_scenarios import (
    PRIORITY_SCENARIO_FAMILIES,
    review_priority_family_scenarios,
)
from examples.problem_corpus.hardening import review_benchmark_hardening


class BenchmarkHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage = review_benchmark_coverage()
        cls.family_scenarios = review_priority_family_scenarios()
        cls.conformance = review_conformance_seeds()
        cls.hardening = review_benchmark_hardening()

    def test_variant_depth_target_is_met(self):
        self.assertTrue(self.coverage.ok, self.coverage.format_text())
        self.assertEqual(150, self.coverage.variant_total)
        self.assertGreaterEqual(self.coverage.variant_min_cases, 8)
        self.assertLessEqual(self.coverage.variant_max_cases, 15)
        self.assertEqual((), self.coverage.variants_below_target)

    def test_family_case_kind_and_bug_class_matrix_is_complete(self):
        self.assertEqual((), self.coverage.families_missing_required_case_kinds)
        self.assertEqual((), self.coverage.families_missing_required_bug_classes)
        self.assertEqual(25, len(self.coverage.family_case_kind_matrix))
        self.assertEqual(25, len(self.coverage.family_bug_class_matrix))
        for _family, bug_classes in self.coverage.family_bug_class_matrix:
            self.assertGreaterEqual(len(bug_classes), 11)

    def test_priority_non_job_matching_family_scenarios_are_strong(self):
        self.assertTrue(self.family_scenarios.ok, self.family_scenarios.format_text())
        self.assertEqual(len(PRIORITY_SCENARIO_FAMILIES), self.family_scenarios.priority_family_count)
        for result in self.family_scenarios.results:
            self.assertTrue(result.ok, result.to_dict())
            self.assertGreater(result.pass_cases, 0)
            self.assertGreater(result.expected_violations_observed, 0)
            self.assertEqual(6, result.variant_count)
            self.assertGreaterEqual(len(result.bug_classes), 11)

    def test_conformance_seed_replay_covers_all_benchmark_families(self):
        self.assertTrue(self.conformance.ok, self.conformance.format_text())
        self.assertEqual(26, self.conformance.production_conformance_family_count)
        self.assertEqual(25, self.conformance.benchmark_conformance_family_count)
        self.assertEqual(78, self.conformance.total_replays)
        self.assertEqual(26, self.conformance.passed)
        self.assertEqual(52, self.conformance.expected_violations_observed)
        self.assertEqual(0, self.conformance.failures)

    def test_combined_hardening_report_is_structured(self):
        self.assertTrue(self.hardening.ok, self.hardening.format_text())
        data = self.hardening.to_dict()
        self.assertTrue(data["coverage_audit"]["ok"])
        self.assertTrue(data["family_scenario_report"]["ok"])
        self.assertTrue(data["conformance_seed_report"]["ok"])

    def test_hardening_runner_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/problem_corpus/run_benchmark_hardening.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("variant_min_cases: 13", completed.stdout)
        self.assertIn("production_conformance_family_count: 26", completed.stdout)
        self.assertIn("benchmark_conformance_family_count: 25", completed.stdout)


if __name__ == "__main__":
    unittest.main()
