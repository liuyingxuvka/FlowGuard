import subprocess
import sys
import unittest

from examples.flowguard_self_review.conformance import (
    generate_self_review_representative_traces,
    replay_self_review_trace,
    trace_for_self_review_scenario,
)
from examples.flowguard_self_review.orchestrator import (
    BrokenNoConformanceOrchestrator,
    BrokenToolchainSubstituteOrchestrator,
    CorrectFlowguardOrchestrator,
)


class FlowguardSelfReviewConformanceTests(unittest.TestCase):
    def test_correct_orchestrator_replays_representative_traces(self):
        traces = generate_self_review_representative_traces()

        self.assertEqual(3, len(traces))
        for trace in traces:
            report = replay_self_review_trace(trace, CorrectFlowguardOrchestrator())
            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(len(trace.steps), len(report.replayed_steps))

    def test_broken_orchestrator_missing_conformance_is_caught(self):
        trace = trace_for_self_review_scenario("FGS03_production_change_runs_conformance")

        report = replay_self_review_trace(trace, BrokenNoConformanceOrchestrator())

        self.assertFalse(report.ok)
        self.assertIsNotNone(report.failed_step_index)
        self.assertIn("conformance", report.format_text())

    def test_broken_toolchain_substitute_is_caught(self):
        trace = trace_for_self_review_scenario("FGS07_missing_toolchain_blocks_full_adoption")

        report = replay_self_review_trace(trace, BrokenToolchainSubstituteOrchestrator())

        self.assertFalse(report.ok)
        self.assertIsNotNone(report.failed_step_index)
        self.assertIn("toolchain", report.format_text())

    def test_self_review_conformance_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_self_review/run_conformance.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard self-review conformance", completed.stdout)
        self.assertIn("correct_status: OK", completed.stdout)

    def test_self_review_conformance_cli_wrapper_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "-m", "flowguard", "self-conformance"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard self-review conformance", completed.stdout)
        self.assertIn("correct_status: OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
