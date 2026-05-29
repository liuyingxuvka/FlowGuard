import subprocess
import sys
import unittest
from pathlib import Path

from flowguard import (
    CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    review_flowguard_closure_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class FlowGuardClosureContractModelTests(unittest.TestCase):
    def test_closure_contract_model_runner_succeeds(self):
        completed = subprocess.run(
            [sys.executable, ".flowguard/flowguard_closure_contract/run_checks.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Scenario: good_closure_contract", completed.stdout)
        self.assertIn("Scenario: broken_point_evidence_completion", completed.stdout)
        self.assertIn("broken_optional_mode", completed.stdout)

    def test_closure_can_require_runtime_path_alignment_report(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:runtime-path",
                evidence_reports=(
                    ClosureEvidenceReport(
                        "runtime-path:checkout",
                        CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT,
                        decision="runtime_path_alignment_green",
                    ),
                ),
                require_runtime_path_alignment=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_missing_runtime_path_alignment_blocks_full_closure(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:runtime-path",
                require_runtime_path_alignment=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_runtime_path_alignment", [finding.code for finding in report.findings])


if __name__ == "__main__":
    unittest.main()
