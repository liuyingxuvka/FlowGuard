import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CLAIM_SCOPE_FULL,
    PPA_DISPOSITION_PRESERVE_FACADE,
    review_primary_path_authority,
)


def primary(**kwargs):
    defaults = {
        "business_path_id": "submit_order",
        "business_intent": "submit order",
        "primary_entrypoint_id": "orders.submit.primary",
        "owner_model_id": "orders.submit.model",
        "owner_code_contract_id": "orders.submit.contract",
        "expected_terminal": "accepted_or_visible_error",
        "evidence_ids": ("runtime:submit-order:no-fallback",),
    }
    defaults.update(kwargs)
    return PrimaryPathContract(**defaults)


def good_facade(**kwargs):
    defaults = {
        "candidate_path_id": "orders.submit.v1",
        "fallback_for_path_id": "submit_order",
        "business_intent": "submit order",
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
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("primary_path_authority_green", report.decision)
        self.assertIn("submit_order", report.primary_path_ids)
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
                    primary(primary_entrypoint_id="orders.submit.alternate"),
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


if __name__ == "__main__":
    unittest.main()
