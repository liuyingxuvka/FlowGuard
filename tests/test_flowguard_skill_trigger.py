import subprocess
import sys
import unittest

from examples.flowguard_skill_trigger.model import run_skill_trigger_review


class FlowguardSkillTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_skill_trigger_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_skill_trigger_catalog_matches_expectations(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(21, self.report.total_scenarios)
        self.assertEqual(13, self.report.passed)
        self.assertEqual(7, self.report.expected_violations_observed)
        self.assertEqual(1, self.report.needs_human_review)

    def test_correct_trigger_scenarios_pass_or_need_review(self):
        for name in (
            "STS01_architecture_change_triggers_skill",
            "STS02_ui_state_flow_triggers_skill",
            "STS03_trivial_docs_skips_with_reason",
            "STS04_read_only_question_skips_with_reason",
            "STS06_argument_flow_triggers_skill",
            "STS07_decision_flow_triggers_skill",
            "STS08_multi_model_project_requires_model_mesh",
            "STS09_process_flow_routes_directly",
            "STS10_model_test_alignment_routes_directly",
            "STS11_test_mesh_routes_directly",
            "STS12_structure_mesh_routes_directly",
            "STS13_model_miss_routes_directly",
            "STS14_existing_model_preflight_routes_directly",
        ):
            self.assertEqual("pass", self.statuses[name])
        self.assertEqual(
            "needs_human_review",
            self.statuses["STS05_ambiguous_scope_needs_human_review"],
        )

    def test_broken_trigger_variants_are_caught(self):
        expected = {
            "STB01_broken_skips_risky_architecture",
            "STB02_broken_overtriggers_trivial_docs",
            "STB03_broken_missing_conformance",
            "STB04_broken_skip_without_reason",
            "STB05_broken_in_progress_evidence_finalized",
            "STB06_broken_ambiguous_scope_skipped",
            "STB07_broken_missing_model_mesh",
        }
        for name in expected:
            self.assertEqual("expected_violation_observed", self.statuses[name])

    def test_skill_trigger_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_skill_trigger/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard Skill trigger review", completed.stdout)
        self.assertIn("needs human review: 1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
