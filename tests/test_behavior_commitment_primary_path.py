import unittest

from flowguard import (
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_SCOPE_FULL,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorPathAuthorityBinding,
    BehaviorSourceSurface,
    FallbackPathCandidate,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_CLAIM_SCOPE_FULL,
    PPA_DISPOSITION_UNKNOWN,
    PPA_TRIGGER_PRIMARY_FAILURE,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    behavior_path_binding_from_primary_path_report,
    review_behavior_commitment_ledger,
    review_primary_path_authority,
)


def primary_report(*, blocked=False):
    primary = PrimaryPathContract(
        "submit_order",
        business_intent="submit order",
        primary_entrypoint_id="orders.submit.primary",
        owner_model_id="orders.submit.model",
        owner_code_contract_id="orders.submit.contract",
        expected_terminal="accepted_or_visible_error",
        evidence_ids=("runtime:submit-order:no-fallback",),
    )
    candidates = ()
    if blocked:
        candidates = (
            FallbackPathCandidate(
                "orders.submit.fallback",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                candidate_behavior=PPA_BEHAVIOR_RETURN_SUCCESS,
                invokes_on_primary_failure=True,
                returns_success_after_primary_failure=True,
                disposition=PPA_DISPOSITION_UNKNOWN,
            ),
        )
    return review_primary_path_authority(
        PrimaryPathAuthorityPlan(
            "submit-order-authority",
            primary_paths=(primary,),
            fallback_candidates=candidates,
            claim_scope=PPA_CLAIM_SCOPE_FULL,
            coverage_case_ids=("ppa.case",),
            coverage_shard_ids=("contract_shard:primary_path_authority:core_no_fallback",),
            coverage_receipt_ids=("contract_coverage:primary_path_authority",),
            risk_gate_ids=("risk_gate:primary_path_authority", "risk_gate:primary_path_authority_cartesian_coverage"),
        )
    )


def behavior_ledger(path_authority):
    return BehaviorCommitmentLedger(
        "ledger",
        project_boundary="orders",
        current_revision="rev-1",
        claim_scope=BCL_SCOPE_FULL,
        owner="maintainer",
        validation_boundary="orders release",
        rationale="orders behavior ledger",
        expected_commitment_ids=("commitment:submit-order",),
        source_surfaces=(
            BehaviorSourceSurface(
                "surface:api-submit-order",
                surface_kind="api",
                source_ref="orders/api.py",
                commitment_ids=("commitment:submit-order",),
                owner="api-owner",
                validation_boundary="API contract",
                rationale="public API exposes submit order",
            ),
        ),
        commitments=(
            BehaviorCommitment(
                "commitment:submit-order",
                label="submit order",
                actor="API client",
                trigger="calls submit order",
                expected_result="accepted order or visible error",
                failure_boundary="primary path failure is visible",
                source_surface_ids=("surface:api-submit-order",),
                primary_owner_model_id="orders.submit.model",
                validation_boundary="model, API contract, runtime no-fallback evidence",
                rationale="path-sensitive external order submission",
                path_authority=path_authority,
                evidence=BehaviorEvidenceBinding(
                    model_obligation_ids=("obligation:submit-order",),
                    code_contract_ids=("contract:submit-order",),
                    test_evidence_ids=("test:submit-order",),
                    risk_gate_ids=("risk_gate:behavior_commitment_coverage:ledger",),
                    evidence_state=BCL_EVIDENCE_CURRENT_PASS,
                    current=True,
                ),
            ),
        ),
    )


def codes(report):
    return {finding.code for finding in report.findings}


class BehaviorCommitmentPrimaryPathTests(unittest.TestCase):
    def test_path_sensitive_commitment_requires_ppa_binding(self):
        report = review_behavior_commitment_ledger(
            behavior_ledger(BehaviorPathAuthorityBinding(path_sensitive=True))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_missing_primary_path_authority", codes(report))
        self.assertIn("commitment:submit-order", report.path_sensitive_commitment_ids)

    def test_passing_ppa_report_satisfies_path_sensitive_commitment(self):
        ppa = primary_report()
        self.assertTrue(ppa.ok, ppa.format_text())
        report = review_behavior_commitment_ledger(
            behavior_ledger(
                behavior_path_binding_from_primary_path_report(
                    ppa,
                    business_intent="submit order",
                    ppa_report_id="report:submit-order-authority",
                )
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("commitment:submit-order", report.path_sensitive_commitment_ids)
        self.assertIn("risk_gate:primary_path_authority", report.required_risk_gate_ids)

    def test_blocked_ppa_report_blocks_commitment(self):
        ppa = primary_report(blocked=True)
        self.assertFalse(ppa.ok)
        report = review_behavior_commitment_ledger(
            behavior_ledger(behavior_path_binding_from_primary_path_report(ppa, business_intent="submit order"))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_primary_path_blocked", codes(report))
        self.assertIn("commitment:submit-order", report.ppa_blocked_commitment_ids)


if __name__ == "__main__":
    unittest.main()
