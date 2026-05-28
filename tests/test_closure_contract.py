import unittest

import flowguard
from flowguard import (
    CLOSURE_CONFIDENCE_FULL,
    CLOSURE_CONFIDENCE_SCOPED,
    CLOSURE_DECISION_BLOCKED,
    CLOSURE_DECISION_FULL,
    CLOSURE_DECISION_SCOPED,
    CLOSURE_REPORT_RISK_LEDGER,
    CLOSURE_REPORT_RUNTIME_GATEWAY,
    MODEL_QUALITY_HIDDEN_STATE,
    ArtifactInvalidation,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    ModelQualitySignal,
    RuntimeGatewayInventoryClosure,
    RuntimeTraceMapping,
    SameClassMissClosure,
    review_flowguard_closure_contract,
)


def evidence_report(report_id="report:risk-ledger", **overrides):
    values = {
        "report_id": report_id,
        "report_kind": CLOSURE_REPORT_RISK_LEDGER,
        "decision": "risk_evidence_full_confidence",
        "ok": True,
        "current": True,
        "confidence": CLOSURE_CONFIDENCE_FULL,
        "result_status": "passed",
        "proof_artifact_ids": ("artifact:risk-ledger",),
    }
    values.update(overrides)
    return ClosureEvidenceReport(**values)


def green_plan(**overrides):
    values = {
        "claim_id": "release:flowguard",
        "runtime_trace_mappings": (
            RuntimeTraceMapping(
                "trace:runtime-route",
                model_obligation_id="model:runtime-route",
                source_evidence_id="artifact:runtime-trace",
            ),
        ),
        "artifact_invalidations": (
            ArtifactInvalidation(
                "artifact:runtime-gateway-code",
                dependent_evidence_ids=("artifact:old-gateway-proof",),
                revalidation_evidence_ids=("artifact:new-gateway-proof",),
            ),
        ),
        "model_quality_signals": (
            ModelQualitySignal(
                "quality:hidden-state-reviewed",
                MODEL_QUALITY_HIDDEN_STATE,
                model_id="model:runtime-route",
                resolved=True,
                resolution_evidence_ids=("artifact:model-quality",),
            ),
        ),
        "same_class_miss_closures": (
            SameClassMissClosure(
                "miss:runtime-route",
                observed_failure_evidence_id="artifact:observed-failure",
                same_class_proof_evidence_id="artifact:same-class-proof",
                model_obligation_id="model:runtime-route",
            ),
        ),
        "runtime_gateway_closures": (
            RuntimeGatewayInventoryClosure(
                "gateway:runtime",
                inventory_source_evidence_ids=("inventory:static-scan", "inventory:runtime-replay"),
                gateway_report_evidence_id="report:runtime-gateway",
            ),
        ),
        "evidence_reports": (
            evidence_report(
                "report:runtime-gateway",
                report_kind=CLOSURE_REPORT_RUNTIME_GATEWAY,
                decision="runtime_gateway_adoption_green",
                proof_artifact_ids=("artifact:runtime-gateway",),
            ),
            evidence_report(),
        ),
    }
    values.update(overrides)
    return FlowGuardClosureContractPlan(**values)


def finding_codes(report):
    return [finding.code for finding in report.findings]


class FlowGuardClosureContractTests(unittest.TestCase):
    def test_complete_closure_contract_supports_full_confidence(self):
        report = review_flowguard_closure_contract(green_plan())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(CLOSURE_DECISION_FULL, report.decision)
        self.assertEqual(CLOSURE_CONFIDENCE_FULL, report.confidence)
        self.assertEqual((), report.findings)

    def test_unmapped_runtime_trace_is_model_miss_boundary(self):
        report = review_flowguard_closure_contract(
            green_plan(
                runtime_trace_mappings=(
                    RuntimeTraceMapping("trace:unmapped", source_evidence_id="artifact:trace"),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(CLOSURE_DECISION_BLOCKED, report.decision)
        self.assertIn("runtime_trace_unmapped_model_obligation", finding_codes(report))

    def test_changed_artifact_without_revalidation_blocks(self):
        report = review_flowguard_closure_contract(
            green_plan(
                artifact_invalidations=(
                    ArtifactInvalidation(
                        "artifact:changed-gateway",
                        dependent_evidence_ids=("artifact:old-proof",),
                        revalidation_evidence_ids=(),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("artifact_change_missing_revalidation", finding_codes(report))

    def test_unresolved_model_quality_signal_blocks(self):
        report = review_flowguard_closure_contract(
            green_plan(
                model_quality_signals=(
                    ModelQualitySignal(
                        "quality:hidden-state-open",
                        MODEL_QUALITY_HIDDEN_STATE,
                        model_id="model:runtime-route",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("model_quality_gap_open", finding_codes(report))

    def test_missing_same_class_proof_blocks(self):
        report = review_flowguard_closure_contract(
            green_plan(
                same_class_miss_closures=(
                    SameClassMissClosure(
                        "miss:runtime-route",
                        observed_failure_evidence_id="artifact:observed-failure",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_same_class_proof_evidence", finding_codes(report))

    def test_runtime_gateway_inventory_source_is_required(self):
        report = review_flowguard_closure_contract(
            green_plan(
                runtime_gateway_closures=(
                    RuntimeGatewayInventoryClosure(
                        "gateway:runtime",
                        inventory_source_evidence_ids=(),
                        gateway_report_evidence_id="report:runtime-gateway",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_runtime_gateway_inventory_source", finding_codes(report))

    def test_runtime_gateway_path_owner_conflict_blocks(self):
        report = review_flowguard_closure_contract(
            green_plan(
                runtime_gateway_closures=(
                    RuntimeGatewayInventoryClosure(
                        "gateway:runtime",
                        inventory_source_evidence_ids=("inventory:static-scan",),
                        gateway_report_evidence_id="report:runtime-gateway",
                        unresolved_path_owner_conflicts=("card_ack_named_like_role_output",),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("runtime_gateway_path_owner_conflict", finding_codes(report))

    def test_scoped_risk_ledger_downgrades_final_claim(self):
        report = review_flowguard_closure_contract(
            green_plan(
                evidence_reports=(
                    evidence_report(
                        "report:runtime-gateway",
                        report_kind=CLOSURE_REPORT_RUNTIME_GATEWAY,
                        decision="runtime_gateway_adoption_green",
                    ),
                    evidence_report(
                        confidence=CLOSURE_CONFIDENCE_SCOPED,
                        decision="risk_evidence_scoped_confidence",
                    ),
                )
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(CLOSURE_DECISION_SCOPED, report.decision)
        self.assertEqual(CLOSURE_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("closure_report_not_full_confidence", finding_codes(report))
        self.assertIn("risk_ledger_not_full_confidence", finding_codes(report))

    def test_scoped_evidence_blocks_when_scoped_confidence_not_allowed(self):
        report = review_flowguard_closure_contract(
            green_plan(
                allow_scoped_confidence=False,
                evidence_reports=(
                    evidence_report(
                        "report:runtime-gateway",
                        report_kind=CLOSURE_REPORT_RUNTIME_GATEWAY,
                        decision="runtime_gateway_adoption_green",
                    ),
                    evidence_report(
                        confidence=CLOSURE_CONFIDENCE_SCOPED,
                        decision="risk_evidence_scoped_confidence",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(CLOSURE_DECISION_BLOCKED, report.decision)
        self.assertIn("closure_report_not_full_confidence", finding_codes(report))

    def test_public_api_exports_closure_contract(self):
        self.assertIn("FlowGuardClosureContractPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_flowguard_closure_contract", flowguard.REPORTING_HELPER_API)
        self.assertIn("closure_contract_template_files", flowguard.EVIDENCE_API)
        self.assertTrue(hasattr(flowguard, "RuntimeTraceMapping"))


if __name__ == "__main__":
    unittest.main()
