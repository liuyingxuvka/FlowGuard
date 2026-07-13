import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    ProofArtifactRef,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CLAIM_SCOPE_FULL,
    PPA_DISPOSITION_PRESERVE_FACADE,
    review_primary_path_authority,
)


INTENT_ID = "intent:submit-order"
COMMITMENT_ID = "commitment:submit-order"
PRIMARY_PATH_ID = "submit_order"


def current_proof():
    return ProofArtifactRef(
        "proof:submit-order-primary",
        producer_route="runtime_path_evidence",
        command="python -m pytest tests/test_primary_path_authority.py -q",
        result_path=".flowguard/evidence/submit-order-primary.json",
        result_status="passed",
        exit_code=0,
        artifact_fingerprints={"orders.submit.contract": "sha256:current"},
        covered_obligation_ids=("obligation:submit-order-primary",),
    )


def primary(**kwargs):
    defaults = {
        "business_path_id": "submit_order",
        "business_intent": "submit order",
        "business_intent_id": INTENT_ID,
        "behavior_commitment_id": COMMITMENT_ID,
        "primary_entrypoint_id": "orders.submit.primary",
        "owner_model_id": "orders.submit.model",
        "owner_code_contract_id": "orders.submit.contract",
        "expected_terminal": "accepted_or_visible_error",
        "evidence_ids": ("runtime:submit-order:no-fallback",),
        "runtime_evidence_state": "current_pass",
        "runtime_observation_ids": ("runtime:submit-order:no-fallback",),
        "required_obligation_ids": ("obligation:submit-order-primary",),
        "proof_artifact": current_proof(),
        "source_surface_ids": ("surface:orders-primary",),
    }
    defaults.update(kwargs)
    return PrimaryPathContract(**defaults)


def good_facade(**kwargs):
    defaults = {
        "candidate_path_id": "orders.submit.v1",
        "fallback_for_path_id": "submit_order",
        "business_intent": "submit order",
        "business_intent_id": INTENT_ID,
        "behavior_commitment_id": COMMITMENT_ID,
        "source_surface_id": "surface:orders-v1",
        "delegates_to_path_id": PRIMARY_PATH_ID,
        "candidate_surface": PPA_CANDIDATE_COMPATIBILITY_FACADE,
        "candidate_behavior": PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
        "classification": PPA_AUTHORITY_EXTERNAL_FACADE,
        "disposition": PPA_DISPOSITION_PRESERVE_FACADE,
        "evidence_refs": ("test:legacy-api-delegates-to-primary",),
        "compatibility_intent": "external API keeps old entrypoint while delegating to primary",
    }
    defaults.update(kwargs)
    return FallbackPathCandidate(**defaults)


def finding_codes(report):
    return {finding.code for finding in report.findings}


class PrimaryPathAuthorityTests(unittest.TestCase):
    def test_good_plan_with_thin_facade_and_coverage_passes(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "submit-order-authority",
                primary_paths=(primary(),),
                fallback_candidates=(good_facade(),),
                claim_scope=PPA_CLAIM_SCOPE_FULL,
                coverage_case_ids=("ppa.core_no_fallback.submit_order.exception.legacy.primary_failure.return_success",),
                coverage_shard_ids=("contract_shard:primary_path_authority:core_no_fallback",),
                coverage_receipt_ids=("contract_coverage:primary_path_authority",),
                risk_gate_ids=("risk_gate:primary_path_authority", "risk_gate:primary_path_authority_cartesian"),
                expected_business_intent_ids=(INTENT_ID,),
                expected_candidate_ids=("orders.submit.v1",),
                expected_surface_ids=("surface:orders-primary", "surface:orders-v1"),
                inventory_revision="orders-surface-inventory:v1",
                inventory_evidence_ids=("inventory:orders-surfaces:v1",),
                preflight_id="preflight:submit-order",
                behavior_commitment_ledger_id="ledger:orders",
                existing_current_path_ids=(PRIMARY_PATH_ID,),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("primary_path_authority_green", report.decision)
        self.assertIn("submit_order", report.primary_path_ids)
        self.assertEqual(PRIMARY_PATH_ID, report.primary_path_id)
        self.assertIn("orders.submit.v1", report.fallback_candidate_ids)

    def test_missing_primary_owner_blocks(self):
        report = review_primary_path_authority(PrimaryPathAuthorityPlan("missing-primary"))

        self.assertFalse(report.ok)
        self.assertIn("missing_primary_authority", finding_codes(report))

    def test_duplicate_primary_authority_blocks(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "duplicate-primary",
                primary_paths=(
                    primary(primary_entrypoint_id="orders.submit.primary"),
                    primary(
                        business_path_id="submit_order_parallel",
                        primary_entrypoint_id="orders.submit.alternate",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("duplicate_primary_runtime_authority", finding_codes(report))

    def test_full_claim_requires_coverage_handoff_ids(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "missing-coverage",
                primary_paths=(primary(),),
                claim_scope=PPA_CLAIM_SCOPE_FULL,
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("primary_path_cartesian_coverage_missing", codes)
        self.assertIn("primary_path_coverage_shards_missing", codes)
        self.assertIn("primary_path_risk_gate_missing", codes)

    def test_complete_inventory_blocks_omitted_candidate_and_surface(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "missing-candidate-inventory",
                primary_paths=(primary(),),
                expected_business_intent_ids=(INTENT_ID,),
                expected_candidate_ids=("orders.submit.v1",),
                expected_surface_ids=("surface:orders-primary", "surface:orders-v1"),
                inventory_revision="orders-surface-inventory:v1",
                inventory_evidence_ids=("inventory:orders-surfaces:v1",),
                preflight_id="preflight:submit-order",
                behavior_commitment_ledger_id="ledger:orders",
                existing_current_path_ids=(PRIMARY_PATH_ID,),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("expected_primary_path_candidate_missing", codes)
        self.assertIn("expected_primary_path_surface_missing", codes)

    def test_equivalent_new_path_requires_explicit_replacement_evidence(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "wrong-equivalent-path",
                primary_paths=(primary(business_path_id="submit_order_parallel"),),
                expected_business_intent_ids=(INTENT_ID,),
                expected_surface_ids=("surface:orders-primary",),
                inventory_revision="orders-surface-inventory:v1",
                inventory_evidence_ids=("inventory:orders-surfaces:v1",),
                preflight_id="preflight:submit-order",
                behavior_commitment_ledger_id="ledger:orders",
                existing_current_path_ids=(PRIMARY_PATH_ID,),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("existing_primary_path_not_reused", finding_codes(report))


if __name__ == "__main__":
    unittest.main()
