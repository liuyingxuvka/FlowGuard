import json
from pathlib import Path
import subprocess
import sys
import unittest

from examples.problem_corpus.matrix import build_problem_corpus, review_problem_corpus
from examples.problem_corpus.taxonomy import (
    FAILURE_MODES,
    GAP_FOCUS_AREAS,
    PRESSURE_FOCUS_AREAS,
    WORKFLOW_FAMILIES,
)


class ProblemCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = build_problem_corpus()
        cls.report = review_problem_corpus()
        cls.case_ids = [case.case_id for case in cls.corpus.cases]

    def test_corpus_quality_report_is_ok(self):
        self.assertTrue(self.report.ok, self.report.format_text())
        self.assertEqual(2100, self.report.total_cases)
        self.assertGreaterEqual(self.report.total_cases, 2100)
        self.assertLessEqual(self.report.total_cases, 2100)

    def test_corpus_has_broad_workflow_and_failure_coverage(self):
        self.assertEqual(len(WORKFLOW_FAMILIES), self.report.workflow_family_count)
        self.assertGreaterEqual(self.report.workflow_family_count, 20)
        self.assertGreaterEqual(self.report.failure_mode_count, len(FAILURE_MODES))
        self.assertGreaterEqual(self.report.failure_mode_count, 20)
        self.assertGreaterEqual(self.report.software_domain_count, 10)

    def test_each_workflow_family_has_enough_cases(self):
        counts = dict(self.report.workflow_family_counts)
        self.assertEqual(25, len(counts))
        self.assertGreaterEqual(min(counts.values()), 50)
        self.assertLessEqual(self.report.max_workflow_family_share, 0.12)

    def test_case_kind_distribution_is_not_happy_path_only(self):
        self.assertEqual(380, self.report.count_case_kind("positive_correct_case"))
        self.assertEqual(724, self.report.count_case_kind("negative_broken_case"))
        self.assertEqual(408, self.report.count_case_kind("boundary_edge_case"))
        self.assertEqual(283, self.report.count_case_kind("invalid_initial_state_case"))
        self.assertEqual(305, self.report.count_case_kind("loop_or_stuck_case"))
        self.assertGreaterEqual(
            self.report.count_case_kind("negative_broken_case"),
            self.report.count_case_kind("positive_correct_case"),
        )

    def test_gap_expansion_is_present_and_distributed(self):
        self.assertEqual(1500, self.report.count_case_source("base_1500"))
        self.assertEqual(500, self.report.count_case_source("gap_500"))
        self.assertEqual(100, self.report.count_case_source("pressure_100"))
        self.assertEqual(len(GAP_FOCUS_AREAS), len(self.report.gap_focus_counts))
        for area in GAP_FOCUS_AREAS:
            self.assertEqual(
                int(area["quota"]),
                self.report.count_gap_focus(str(area["name"])),
                str(area["name"]),
            )
        self.assertEqual(len(PRESSURE_FOCUS_AREAS), len(self.report.pressure_focus_counts))
        for area in PRESSURE_FOCUS_AREAS:
            self.assertEqual(
                int(area["quota"]),
                self.report.count_pressure_focus(str(area["name"])),
                str(area["name"]),
            )

    def test_failure_modes_and_domains_are_not_overconcentrated(self):
        self.assertLessEqual(self.report.top_5_failure_mode_share, 0.45)
        self.assertLessEqual(self.report.max_software_domain_share, 0.20)
        self.assertLessEqual(self.report.near_duplicate_group_max, 8)
        self.assertGreaterEqual(self.report.expected_behavior_uniqueness, 0.70)
        self.assertGreaterEqual(self.report.evidence_uniqueness, 0.70)

    def test_case_ids_are_unique_and_required_fields_are_present(self):
        self.assertEqual(len(self.case_ids), len(set(self.case_ids)))
        self.assertFalse(self.corpus.validate())
        sample = self.corpus.cases[0]
        self.assertTrue(sample.expected_behavior)
        self.assertTrue(sample.evidence_to_check)
        self.assertTrue(sample.forbidden_behavior or sample.non_goals)

    def test_cases_do_not_contain_roadmap_mapping_fields(self):
        forbidden_terms = (
            "phase_11",
            "phase_12",
            "phase_13",
            "phase_14",
            "phase_15",
            "target_phase",
            "future_owner",
            "current_capability",
            "support_status",
            "roadmap",
        )
        for case in self.corpus.cases:
            payload = json.dumps(case.to_dict(), sort_keys=True).lower()
            for term in forbidden_terms:
                self.assertNotIn(term, payload, case.case_id)

    def test_report_exports_json(self):
        loaded = json.loads(self.report.to_json_text())
        self.assertTrue(loaded["ok"])
        self.assertEqual("problem_intent_cases", loaded["count_semantics"])
        self.assertEqual("not_executable_tests", loaded["execution_claim"])
        self.assertEqual(2100, loaded["total_cases"])
        self.assertIn("workflow_family_counts", loaded)
        self.assertIn("gap_focus_counts", loaded)
        self.assertIn("pressure_focus_counts", loaded)

    def test_run_corpus_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/problem_corpus/run_corpus_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("real software problem corpus", completed.stdout)
        self.assertIn("count_semantics: problem_intent_cases", completed.stdout)
        self.assertIn("execution_claim: not_executable_tests", completed.stdout)
        self.assertIn("total_cases: 2100", completed.stdout)
        self.assertIn("gap_500: 500", completed.stdout)
        self.assertIn("pressure_100: 100", completed.stdout)
        self.assertNotIn("executable_tests: 2100", completed.stdout)
        self.assertNotIn("unit_tests: 2100", completed.stdout)

    def test_benchmark_baseline_contract_documents_freeze_rules(self):
        text = Path("docs/benchmark_baseline_contract.md").read_text(encoding="utf-8")
        self.assertIn("total_cases: 2100", text)
        self.assertIn("pressure_100: 100", text)
        self.assertIn("Allowed Changes", text)
        self.assertIn("Disallowed Changes", text)
        self.assertIn("known_limitation", text)


if __name__ == "__main__":
    unittest.main()
