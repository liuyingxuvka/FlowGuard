import json
import subprocess
import sys
import unittest

from examples.problem_corpus.executable import review_executable_corpus


class ExecutableCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = review_executable_corpus()
        cls.results = cls.report.results

    def test_all_problem_cases_are_executable(self):
        self.assertTrue(self.report.ok, self.report.format_text())
        self.assertEqual(2100, self.report.total_cases)
        self.assertEqual(2100, self.report.executable_cases)
        self.assertEqual(0, self.report.not_executable_yet)
        self.assertEqual(1.0, self.report.coverage_ratio)
        self.assertTrue(self.report.coverage_complete)
        self.assertEqual(2100, self.report.accepted_executable_cases)
        self.assertEqual(0, self.report.failure_cases)
        self.assertEqual(0, self.report.count_status("not_executable_yet"))
        self.assertEqual(2100, self.report.real_model_cases)
        self.assertEqual(0, self.report.generic_fallback_cases)
        self.assertEqual(150, self.report.model_variant_total)
        self.assertEqual(25, self.report.model_families_with_six_variants)

    def test_expected_vs_observed_status_counts_are_stable(self):
        self.assertEqual(788, self.report.count_status("pass"))
        self.assertEqual(1312, self.report.count_status("expected_violation_observed"))
        self.assertEqual(0, self.report.count_status("known_limitation"))
        self.assertEqual(0, self.report.count_status("unexpected_violation"))
        self.assertEqual(0, self.report.count_status("missing_expected_violation"))
        self.assertEqual(0, self.report.count_status("oracle_mismatch"))

    def test_execution_kinds_are_real_domain_model_checkers(self):
        self.assertEqual(1795, self.report.count_execution_kind("real_model_workflow"))
        self.assertEqual(305, self.report.count_execution_kind("real_model_loop"))
        for result in self.results:
            joined_evidence = "\n".join(result.evidence)
            metadata = dict(result.metadata)
            self.assertEqual("real_domain_model", metadata.get("model_binding_kind"))
            self.assertEqual("false", metadata.get("generic_fallback"))
            self.assertTrue(metadata.get("model_family"))
            self.assertTrue(metadata.get("model_variant"))
            self.assertTrue(metadata.get("variant_id"))
            self.assertTrue(metadata.get("variant_title"))
            self.assertTrue(metadata.get("structural_category"))
            self.assertTrue(metadata.get("domain_block_names"))
            self.assertTrue(metadata.get("domain_state_slots"))
            self.assertNotIn("CorpusIngest", metadata.get("domain_block_names", ""))
            self.assertNotIn("CorpusApply", metadata.get("domain_block_names", ""))
            self.assertNotIn("CorpusFinalize", metadata.get("domain_block_names", ""))
            if result.execution_kind == "real_model_workflow":
                self.assertTrue(result.mapped_checker.startswith("RealWorkflow:"))
                self.assertIn("real_checker=RealWorkflow:", joined_evidence)
            elif result.execution_kind == "real_model_loop":
                self.assertTrue(result.mapped_checker.startswith("RealLoopCheck:"))
                self.assertIn("real_checker=RealLoopCheck:", joined_evidence)
            else:
                self.fail(f"unexpected execution kind: {result.execution_kind}")

    def test_negative_cases_have_counterexample_traces(self):
        negatives = [result for result in self.results if result.case_kind == "negative_broken_case"]
        self.assertEqual(724, len(negatives))
        for negative in negatives:
            self.assertEqual("expected_violation_observed", negative.status, negative.case_id)
            self.assertIsNotNone(negative.counterexample_trace, negative.case_id)
            self.assertGreater(len(negative.counterexample_trace.steps), 0, negative.case_id)
            self.assertIn("structural_category=", "\n".join(negative.evidence), negative.case_id)

    def test_invalid_initial_state_cases_are_executed(self):
        invalid_cases = [
            result for result in self.results if result.case_kind == "invalid_initial_state_case"
        ]
        self.assertEqual(283, len(invalid_cases))
        for invalid in invalid_cases:
            self.assertEqual("expected_violation_observed", invalid.status, invalid.case_id)
            self.assertEqual("violation", invalid.expected_status, invalid.case_id)
            self.assertEqual("violation", invalid.observed_status, invalid.case_id)
            self.assertIsNotNone(invalid.counterexample_trace, invalid.case_id)

    def test_loop_cases_have_graph_evidence(self):
        loop_cases = [result for result in self.results if result.case_kind == "loop_or_stuck_case"]
        self.assertEqual(305, len(loop_cases))
        for loop in loop_cases:
            self.assertIn(
                loop.status,
                {"expected_violation_observed", "known_limitation"},
                loop.case_id,
            )
            self.assertEqual("real_model_loop", loop.execution_kind, loop.case_id)
            self.assertIsNotNone(loop.graph_evidence, loop.case_id)
            self.assertIn("graph_summary", loop.graph_evidence, loop.case_id)
            self.assertIn("findings=", "\n".join(loop.evidence), loop.case_id)
            if loop.failure_mode == "cycle_with_escape_without_forced_progress":
                self.assertIn("potential_nontermination", loop.observed_violation_names, loop.case_id)
                self.assertIn("missing_progress_guarantee", loop.observed_violation_names, loop.case_id)

    def test_corpus_sections_and_gap_counts_are_preserved(self):
        self.assertEqual(1500, self.report.count_case_source("base_1500"))
        self.assertEqual(500, self.report.count_case_source("gap_500"))
        self.assertEqual(100, self.report.count_case_source("pressure_100"))
        self.assertEqual(9, len(self.report.gap_focus_counts))
        self.assertEqual(4, len(self.report.pressure_focus_counts))
        self.assertEqual(25, self.report.count_pressure_focus("bounded_progress_and_fairness"))
        self.assertEqual(25, self.report.count_pressure_focus("eventual_obligation_and_temporal_order"))
        self.assertEqual(25, self.report.count_pressure_focus("contract_composition_refinement"))
        self.assertEqual(25, self.report.count_pressure_focus("benchmark_freeze_and_artifact_stability"))

    def test_contract_refinement_pressure_cases_have_contract_evidence(self):
        contract_cases = [
            result
            for result in self.results
            if dict(result.metadata).get("pressure_focus_area") == "contract_composition_refinement"
        ]
        self.assertEqual(25, len(contract_cases))
        for result in contract_cases:
            evidence = "\n".join(result.evidence)
            self.assertEqual("expected_violation_observed", result.status, result.case_id)
            self.assertIn("contract_checked=true", evidence, result.case_id)
            self.assertIn("contract_status=violation", evidence, result.case_id)
            self.assertIn("contract_findings=postcondition", evidence, result.case_id)

    def test_report_exports_json(self):
        loaded = json.loads(self.report.to_json_text(include_results=False))
        self.assertTrue(loaded["ok"])
        self.assertEqual(2100, loaded["total_cases"])
        self.assertEqual(2100, loaded["executable_cases"])
        self.assertEqual(0, loaded["not_executable_yet"])
        self.assertTrue(loaded["coverage_complete"])
        self.assertEqual(1.0, loaded["coverage_ratio"])
        self.assertEqual(0, loaded["failure_cases"])
        self.assertEqual(2100, loaded["real_model_cases"])
        self.assertEqual(0, loaded["generic_fallback_cases"])
        self.assertEqual(150, loaded["model_variant_total"])
        self.assertEqual(25, loaded["model_families_with_six_variants"])
        self.assertIn("model_family_counts", loaded)
        self.assertIn("model_variant_counts", loaded)
        self.assertIn("failure_mode_counts", loaded)
        self.assertIn("oracle_type_counts", loaded)
        self.assertIn("pressure_focus_counts", loaded)
        self.assertEqual([], loaded["results"])

    def test_run_executable_corpus_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/problem_corpus/run_executable_corpus_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("executable corpus review", completed.stdout)
        self.assertIn("total_cases: 2100", completed.stdout)
        self.assertIn("executable_cases: 2100", completed.stdout)
        self.assertIn("not_executable_yet: 0", completed.stdout)
        self.assertIn("coverage_complete: True", completed.stdout)
        self.assertIn("real_model_cases: 2100", completed.stdout)
        self.assertIn("generic_fallback_cases: 0", completed.stdout)
        self.assertIn("model_variant_total: 150", completed.stdout)
        self.assertIn("model_families_with_six_variants: 25", completed.stdout)


if __name__ == "__main__":
    unittest.main()
