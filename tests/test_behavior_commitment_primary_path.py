import unittest

from flowguard import (
    BCL_ACTOR_EXTERNAL_SYSTEM,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_PLANE_PRODUCT_RUNTIME,
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
    ProofArtifactRef,
    behavior_path_binding_from_primary_path_report,
    review_behavior_commitment_ledger,
    review_primary_path_authority,
)


INTENT_ID = "intent:submit-order"
COMMITMENT_ID = "commitment:submit-order"
PRIMARY_PATH_ID = "submit_order"


def current_proof():
    return ProofArtifactRef(
        "proof:submit-order-primary",
        producer_route="runtime_path_evidence",
        command="python -m pytest tests/test_behavior_commitment_primary_path.py -q",
        result_path=".flowguard/evidence/submit-order-primary.json",
        result_status="passed",
        exit_code=0,
        artifact_fingerprints={"orders.submit.contract": "sha256:current"},
        covered_obligation_ids=("obligation:submit-order-primary",),
    )


def primary_report(*, blocked=False):
    primary = PrimaryPathContract(
        PRIMARY_PATH_ID,
        business_intent="submit order",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_entrypoint_id="orders.submit.primary",
        owner_model_id="orders.submit.model",
        owner_code_contract_id="orders.submit.contract",
        expected_terminal="accepted_or_visible_error",
        evidence_ids=("runtime:submit-order:no-fallback",),
        runtime_evidence_state="current_pass",
        runtime_observation_ids=("runtime:submit-order:no-fallback",),
        required_obligation_ids=("obligation:submit-order-primary",),
        proof_artifact=current_proof(),
        source_surface_ids=("surface:api-submit-order",),
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
            expected_business_intent_ids=(INTENT_ID,),
            expected_surface_ids=("surface:api-submit-order",),
            inventory_revision="orders-surface-inventory:v1",
            inventory_evidence_ids=("inventory:orders-surfaces:v1",),
            preflight_id="preflight:submit-order",
            behavior_commitment_ledger_id="ledger:orders",
            existing_current_path_ids=(PRIMARY_PATH_ID,),
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
        expected_business_intent_ids=(INTENT_ID,),
        source_surfaces=(
            BehaviorSourceSurface(
                "surface:api-submit-order",
                surface_kind="api",
                source_ref="orders/api.py",
                commitment_ids=("commitment:submit-order",),
                business_intent_ids=(INTENT_ID,),
                primary_path_id=PRIMARY_PATH_ID,
                owner="api-owner",
                validation_boundary="API contract",
                rationale="public API exposes submit order",
            ),
        ),
        commitments=(
            BehaviorCommitment(
                "commitment:submit-order",
                business_intent_id=INTENT_ID,
                label="submit order",
                behavior_plane=BCL_PLANE_PRODUCT_RUNTIME,
                actor_kind=BCL_ACTOR_EXTERNAL_SYSTEM,
                actor="API client",
                trigger="calls submit order",
                expected_result="accepted order or visible error",
                expected_terminal="accepted order or visible error",
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
    def test_one_item_legacy_plural_migrates_to_canonical_singular_path(self):
        binding = BehaviorPathAuthorityBinding(primary_path_ids=(PRIMARY_PATH_ID,))

        self.assertEqual(PRIMARY_PATH_ID, binding.primary_path_id)
        self.assertTrue(binding.legacy_plural_migrated)
        self.assertEqual(PRIMARY_PATH_ID, binding.to_dict()["primary_path_id"])
        self.assertNotIn("primary_path_ids", binding.to_dict())

    def test_ambiguous_legacy_plural_blocks_path_sensitive_commitment(self):
        binding = BehaviorPathAuthorityBinding(
            path_sensitive=True,
            business_intent_id=INTENT_ID,
            behavior_commitment_id=COMMITMENT_ID,
            ppa_report_id="report:ambiguous",
            ppa_decision="primary_path_authority_green",
            ppa_confidence="full",
            ppa_ok=True,
            primary_path_ids=(PRIMARY_PATH_ID, "submit_order_parallel"),
            runtime_observation_ids=("runtime:ambiguous",),
            proof_artifact_ids=("proof:ambiguous",),
            evidence_current=True,
            ppa_risk_gate_ids=("risk_gate:primary_path_authority",),
        )
        report = review_behavior_commitment_ledger(behavior_ledger(binding))

        self.assertFalse(report.ok)
        self.assertIn("commitment_primary_path_migration_ambiguous", codes(report))

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
