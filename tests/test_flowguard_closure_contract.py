import subprocess
import sys
import unittest
from pathlib import Path

import flowguard
from flowguard import (
    CLOSURE_REPORT_FIELD_LIFECYCLE,
    CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    review_flowguard_closure_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class FlowGuardClosureContractModelTests(unittest.TestCase):
    def _field_lifecycle_report(self, *, old_disposition: str = flowguard.FIELD_DISPOSITION_MIGRATED):
        projection = flowguard.FieldProjection(
            "projection:mode",
            "field:mode",
            model_obligation_id="field:mode:obligation",
            code_contract_id="contract:mode",
            external_inputs=("mode",),
            external_outputs=("mode applied",),
            state_reads=("mode",),
            state_writes=("mode",),
            required_test_kinds=(flowguard.TEST_KIND_HAPPY_PATH,),
        )
        return flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode", "field:old_mode"),
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                        projection=projection,
                    ),
                    flowguard.FieldLifecycleRow(
                        "field:old_mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        lifecycle=flowguard.FIELD_LIFECYCLE_REPLACED,
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                        replacement_field_id="field:mode",
                        disposition=old_disposition,
                        disposition_evidence_refs=("test_old_mode_migrates",)
                        if old_disposition != flowguard.FIELD_DISPOSITION_UNKNOWN
                        else (),
                        projection=projection,
                    ),
                ),
            )
        )

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

    def test_closure_can_require_field_lifecycle_report(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:fields",
                field_lifecycle_reports=(self._field_lifecycle_report(),),
                require_field_lifecycle=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_closure_can_use_field_lifecycle_evidence_report(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:fields",
                evidence_reports=(
                    ClosureEvidenceReport(
                        "fields:checkout",
                        CLOSURE_REPORT_FIELD_LIFECYCLE,
                        decision=flowguard.FIELD_DECISION_FULL,
                    ),
                ),
                require_field_lifecycle=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_missing_field_lifecycle_blocks_when_required(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:fields",
                require_field_lifecycle=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_field_lifecycle_evidence", [finding.code for finding in report.findings])

    def test_blocked_field_lifecycle_blocks_closure(self):
        report = review_flowguard_closure_contract(
            FlowGuardClosureContractPlan(
                "release:fields",
                field_lifecycle_reports=(
                    self._field_lifecycle_report(old_disposition=flowguard.FIELD_DISPOSITION_UNKNOWN),
                ),
                require_field_lifecycle=True,
                require_runtime_trace_mapping=False,
                require_artifact_freshness=False,
                require_model_quality_review=False,
                require_same_class_miss_closure=False,
                require_runtime_gateway_closure=False,
                require_risk_ledger=False,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("field_lifecycle_report_blocked", [finding.code for finding in report.findings])

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
