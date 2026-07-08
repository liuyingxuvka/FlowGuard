import unittest

from flowguard import (
    BCL_CONFIDENCE_FULL,
    RISK_CONFIDENCE_FULL,
    RISK_GATE_BEHAVIOR_COMMITMENT_CARTESIAN_COVERAGE,
    RISK_GATE_BEHAVIOR_COMMITMENT_COVERAGE,
    RISK_PROOF_STATUS_PASSED,
    RiskEvidenceGate,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)


class BehaviorCommitmentReleaseGateTests(unittest.TestCase):
    def test_risk_ledger_requires_behavior_commitment_gates(self):
        proof = RiskEvidenceProof("proof:bcl", result_status=RISK_PROOF_STATUS_PASSED)
        row = RiskEvidenceRow(
            "full-behavior-inventory",
            model_obligation_id="model:bcl",
            code_contract_id="code:bcl",
            proof_evidence_ids=("proof:bcl",),
            gates=(
                RiskEvidenceGate(RISK_GATE_BEHAVIOR_COMMITMENT_COVERAGE),
                RiskEvidenceGate(RISK_GATE_BEHAVIOR_COMMITMENT_CARTESIAN_COVERAGE, "coverage:bcl"),
            ),
        )

        missing = review_risk_evidence_ledger(RiskEvidenceLedgerPlan("ledger", rows=(row,), proof_evidence=(proof,)))
        self.assertFalse(missing.ok)
        self.assertIn("missing_behavior_commitment_coverage_gate", {finding.code for finding in missing.findings})

        full_row = RiskEvidenceRow(
            "full-behavior-inventory",
            model_obligation_id="model:bcl",
            code_contract_id="code:bcl",
            proof_evidence_ids=("proof:bcl",),
            gates=(
                RiskEvidenceGate(
                    RISK_GATE_BEHAVIOR_COMMITMENT_COVERAGE,
                    "coverage:bcl",
                    confidence=RISK_CONFIDENCE_FULL,
                ),
                RiskEvidenceGate(
                    RISK_GATE_BEHAVIOR_COMMITMENT_CARTESIAN_COVERAGE,
                    "cartesian:bcl",
                    confidence=BCL_CONFIDENCE_FULL,
                ),
            ),
        )

        full = review_risk_evidence_ledger(RiskEvidenceLedgerPlan("ledger", rows=(full_row,), proof_evidence=(proof,)))
        self.assertTrue(full.ok, full.format_text())


if __name__ == "__main__":
    unittest.main()
