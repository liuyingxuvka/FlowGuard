import json
import subprocess
import sys
import unittest

from flowguard.baseline import EvidenceCaseResult, build_evidence_baseline_report
from examples.evidence_baseline.baseline import build_current_evidence_baseline


class EvidenceBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_current_evidence_baseline()

    def test_baseline_reaches_upgrade_readiness_target(self):
        self.assertTrue(self.report.ok, self.report.format_text())
        self.assertGreaterEqual(self.report.total_cases, 100)
        self.assertTrue(self.report.meets_target)

    def test_baseline_groups_existing_evidence_sources(self):
        self.assertEqual(30, self.report.count_group("scenario:job_matching"))
        self.assertEqual(14, self.report.count_group("loop:looping_workflow"))
        self.assertEqual(9, self.report.count_group("conformance:job_matching"))
        self.assertEqual(3, self.report.count_group("model_check:job_matching"))
        self.assertGreaterEqual(self.report.count_group("unit_test_inventory"), 39)

    def test_baseline_distinguishes_review_statuses(self):
        self.assertEqual(0, self.report.count_status("unexpected_violation"))
        self.assertEqual(0, self.report.count_status("missing_expected_violation"))
        self.assertEqual(0, self.report.count_status("oracle_mismatch"))
        self.assertGreaterEqual(self.report.count_status("expected_violation_observed"), 20)
        self.assertEqual(2, self.report.count_status("needs_human_review"))
        self.assertEqual(0, self.report.count_status("known_limitation"))

    def test_baseline_covers_key_bug_classes(self):
        required = (
            "duplicate_side_effect",
            "repeated_processing_without_refresh",
            "cache_consistency",
            "state_owner_boundary",
            "source_traceability",
            "downstream_non_consumable_output",
            "non_terminating_component",
            "stuck_state",
            "unreachable_success",
            "progress_fairness",
        )
        for bug_class in required:
            self.assertGreater(
                self.report.count_bug_class(bug_class),
                0,
                bug_class,
            )

    def test_baseline_exports_json(self):
        loaded = json.loads(self.report.to_json_text())
        self.assertTrue(loaded["ok"])
        self.assertGreaterEqual(loaded["total_cases"], 100)
        self.assertIn("bug_class_counts", loaded)

    def test_evidence_baseline_does_not_count_problem_corpus_as_executed(self):
        from examples.problem_corpus.matrix import review_problem_corpus

        corpus = review_problem_corpus()
        self.assertEqual(2100, corpus.total_cases)
        self.assertEqual("problem_intent_cases", corpus.count_semantics)
        self.assertEqual(0, self.report.count_group("problem_intent_corpus"))
        self.assertNotEqual(corpus.total_cases, self.report.count_group("unit_test_inventory"))
        for result in self.report.results:
            self.assertNotEqual("problem_intent_corpus", result.group)
            self.assertNotIn("problem_corpus_case_id", dict(result.metadata))

    def test_generic_scorecard_marks_missing_target_as_not_ok(self):
        report = build_evidence_baseline_report(
            (
                EvidenceCaseResult(
                    name="tiny",
                    group="unit",
                    bug_class="example",
                    expected="OK",
                    observed="OK",
                    status="pass",
                ),
            ),
            target_cases=2,
        )

        self.assertFalse(report.ok)
        self.assertFalse(report.meets_target)

    def test_run_baseline_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/evidence_baseline/run_baseline.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard evidence baseline", completed.stdout)
        self.assertIn("total_cases", completed.stdout)


if __name__ == "__main__":
    unittest.main()
