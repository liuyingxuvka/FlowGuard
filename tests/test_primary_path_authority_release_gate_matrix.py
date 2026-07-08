import unittest

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    RISK_CONFIDENCE_FULL,
    RISK_GATE_PRIMARY_PATH_AUTHORITY,
    RISK_GATE_PRIMARY_PATH_AUTHORITY_CARTESIAN_COVERAGE,
    RISK_PROOF_STATUS_PASSED,
    TEST_LAYER_CONTRACT_COMBINATION_SHARD,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_risk_evidence_ledger,
    review_test_mesh,
)


class PrimaryPathAuthorityReleaseGateMatrixTests(unittest.TestCase):
    def test_test_mesh_consumes_primary_path_shard(self):
        shard_id = "contract_shard:primary_path_authority:core_no_fallback"
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="primary-path-authority",
                partition_items=(
                    TestPartitionItem(shard_id, item_type="contract_coverage_shard", owner_suite_id="ppa-shards"),
                ),
                child_suites=(
                    TestSuiteEvidence(
                        "ppa-shards",
                        layer=TEST_LAYER_CONTRACT_COMBINATION_SHARD,
                        result_status="passed",
                        evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                        test_count=1,
                        selected_count=1,
                        owned_coverage_shard_ids=(shard_id,),
                    ),
                ),
                target_split_derivation=TestTargetSplitDerivation(
                    "primary-path-authority-model",
                    target_suite_ids=("ppa-shards",),
                    covered_partition_item_ids=(shard_id,),
                    rationale="derived from primary path authority coverage universe",
                ),
                required_coverage_shard_ids=(shard_id,),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_risk_ledger_requires_primary_path_gates(self):
        row = RiskEvidenceRow(
            "no-silent-fallback",
            model_obligation_id="model:ppa",
            code_contract_id="code:ppa",
            proof_evidence_ids=("proof:ppa",),
            gates=(
                RiskEvidenceGate(RISK_GATE_PRIMARY_PATH_AUTHORITY),
                RiskEvidenceGate(RISK_GATE_PRIMARY_PATH_AUTHORITY_CARTESIAN_COVERAGE, "coverage:ppa"),
            ),
        )
        proof = RiskEvidenceProof("proof:ppa", result_status=RISK_PROOF_STATUS_PASSED)

        missing = review_risk_evidence_ledger(RiskEvidenceLedgerPlan("ledger", rows=(row,), proof_evidence=(proof,)))
        self.assertFalse(missing.ok)
        self.assertIn("missing_primary_path_authority_gate", {finding.code for finding in missing.findings})

        full_row = RiskEvidenceRow(
            "no-silent-fallback",
            model_obligation_id="model:ppa",
            code_contract_id="code:ppa",
            proof_evidence_ids=("proof:ppa",),
            gates=(
                RiskEvidenceGate(RISK_GATE_PRIMARY_PATH_AUTHORITY, "authority:ppa", confidence=RISK_CONFIDENCE_FULL),
                RiskEvidenceGate(
                    RISK_GATE_PRIMARY_PATH_AUTHORITY_CARTESIAN_COVERAGE,
                    "coverage:ppa",
                    confidence=RISK_CONFIDENCE_FULL,
                ),
            ),
        )
        full = review_risk_evidence_ledger(RiskEvidenceLedgerPlan("ledger", rows=(full_row,), proof_evidence=(proof,)))
        self.assertTrue(full.ok, full.format_text())


if __name__ == "__main__":
    unittest.main()
