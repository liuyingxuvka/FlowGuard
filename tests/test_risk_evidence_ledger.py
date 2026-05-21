import unittest

from flowguard import (
    RISK_CONFIDENCE_BLOCKED,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_LEDGER_DECISION_FULL,
    RISK_LEDGER_DECISION_SCOPED,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_FAILED,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_STALE,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)


def proof(evidence_id="e1", **kwargs):
    return RiskEvidenceProof(
        evidence_id,
        result_status=kwargs.pop("result_status", RISK_PROOF_STATUS_PASSED),
        **kwargs,
    )


def row(risk_id="r1", **kwargs):
    return RiskEvidenceRow(
        risk_id,
        model_obligation_id=kwargs.pop("model_obligation_id", "model:r1"),
        proof_evidence_ids=kwargs.pop("proof_evidence_ids", ("e1",)),
        **kwargs,
    )


def plan(*, rows=None, proof_evidence=None, **kwargs):
    return RiskEvidenceLedgerPlan(
        "ledger",
        rows=tuple(rows if rows is not None else (row(),)),
        proof_evidence=tuple(proof_evidence if proof_evidence is not None else (proof(),)),
        **kwargs,
    )


def finding_codes(report):
    return [finding.code for finding in report.findings]


class RiskEvidenceLedgerTests(unittest.TestCase):
    def test_full_confidence_requires_model_obligation_and_current_external_pass(self):
        report = review_risk_evidence_ledger(plan())

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_FULL, report.decision)
        self.assertEqual(RISK_CONFIDENCE_FULL, report.confidence)
        self.assertIn("status: OK", report.format_text())

    def test_missing_model_or_code_contract_blocks_full_claim(self):
        missing_model = review_risk_evidence_ledger(plan(rows=(row(model_obligation_id=""),)))
        self.assertFalse(missing_model.ok)
        self.assertEqual(RISK_CONFIDENCE_BLOCKED, missing_model.confidence)
        self.assertIn("missing_model_obligation", finding_codes(missing_model))

        missing_contract = review_risk_evidence_ledger(
            plan(require_code_contracts=True, rows=(row(code_contract_id=""),))
        )
        self.assertFalse(missing_contract.ok)
        self.assertEqual("missing_code_contract", missing_contract.decision)

    def test_missing_unknown_duplicate_and_parent_evidence_gaps_are_visible(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(
                    row("r1", proof_evidence_ids=("missing",)),
                    row("r1", parent_model_evidence_required=True, parent_model_evidence_current=False),
                ),
                proof_evidence=(proof("e1"), proof("e1")),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertEqual("duplicate_risk_id", report.decision)
        self.assertIn("duplicate_evidence_id", codes)
        self.assertIn("unknown_evidence_reference", codes)
        self.assertIn("parent_model_evidence_gap", codes)

    def test_stale_skipped_failed_and_progress_only_do_not_count_as_pass(self):
        for status in (
            RISK_PROOF_STATUS_FAILED,
            RISK_PROOF_STATUS_SKIPPED,
            RISK_PROOF_STATUS_STALE,
            RISK_PROOF_STATUS_PROGRESS_ONLY,
        ):
            with self.subTest(status=status):
                report = review_risk_evidence_ledger(
                    plan(proof_evidence=(proof(result_status=status),))
                )
                codes = finding_codes(report)
                self.assertFalse(report.ok)
                self.assertIn("proof_evidence_not_passing", codes)
                self.assertIn("missing_current_passing_proof", codes)

    def test_stale_route_gap_blocks_even_when_status_says_passed(self):
        report = review_risk_evidence_ledger(
            plan(
                proof_evidence=(
                    proof(current=False, stale_reasons=("source_changed",), route_gap_codes=("child_missing",)),
                )
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("route_gap_visible", codes)
        self.assertIn("stale_proof_evidence", codes)
        self.assertIn("missing_current_passing_proof", codes)

    def test_internal_path_only_evidence_blocks_external_contract_claim(self):
        report = review_risk_evidence_ledger(
            plan(proof_evidence=(proof(assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("internal_path_only_evidence", report.decision)

    def test_scoped_out_risk_with_reason_downgrades_confidence_without_blocking(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(
                    row(),
                    row(
                        "r2",
                        in_scope=False,
                        out_of_scope_reason="release-only browser journey is tracked separately",
                        proof_evidence_ids=(),
                        model_obligation_id="",
                    ),
                )
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("scoped_out_risk", finding_codes(report))

    def test_scoped_out_required_risk_without_reason_blocks(self):
        report = review_risk_evidence_ledger(
            plan(rows=(row(in_scope=False, out_of_scope_reason=""),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("scoped_out_required_risk", report.decision)

    def test_overclaim_blocks_full_confidence(self):
        report = review_risk_evidence_ledger(plan(rows=(row(overclaims_full_confidence=True),)))

        self.assertFalse(report.ok)
        self.assertEqual("proof_overclaims_full_confidence", report.decision)


if __name__ == "__main__":
    unittest.main()
