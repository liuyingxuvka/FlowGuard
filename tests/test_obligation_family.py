import unittest

import flowguard
from flowguard import (
    ANALOGOUS_DISPOSITION_COVERED_CURRENT,
    ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON,
    ANALOGOUS_DISPOSITION_SEPARATE_CHANGE,
    ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN,
    FAMILY_CONFIDENCE_BLOCKED,
    FAMILY_CONFIDENCE_FULL,
    FAMILY_CONFIDENCE_SCOPED,
    FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,
    FAMILY_EVIDENCE_PROVENANCE_MANUAL_EVENT,
    FAMILY_EVIDENCE_STATUS_PASSED,
    AnalogousDefectCandidate,
    ObligationFamily,
    ObligationFamilyEvidence,
    ObligationFamilyMember,
    FamilyBadCaseSeed,
    derive_same_class_bad_cases,
    review_analogous_defect_scan,
    review_obligation_family_parity,
)


def family(**kwargs):
    defaults = {
        "family_id": "packet-result",
        "required_mechanisms": ("result_envelope_to_return_event",),
        "allowed_provenance": (FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,),
        "members": (
            ObligationFamilyMember("material", obligation_ids=("obligation:material",)),
            ObligationFamilyMember("research", obligation_ids=("obligation:research",)),
        ),
    }
    defaults.update(kwargs)
    return ObligationFamily(**defaults)


def evidence(evidence_id, member_id, **kwargs):
    defaults = {
        "family_id": "packet-result",
        "member_id": member_id,
        "mechanism_id": "result_envelope_to_return_event",
        "provenance": FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,
        "result_status": FAMILY_EVIDENCE_STATUS_PASSED,
        "current": True,
        "covered_obligations": (f"obligation:{member_id}",),
    }
    defaults.update(kwargs)
    return ObligationFamilyEvidence(evidence_id, **defaults)


def finding_codes(report):
    return [finding.code for finding in report.findings]


class ObligationFamilyParityTests(unittest.TestCase):
    def test_complete_family_matrix_passes(self):
        report = review_obligation_family_parity(
            (family(),),
            (
                evidence("material-reconcile", "material"),
                evidence("research-reconcile", "research"),
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_FULL, report.confidence)
        self.assertEqual(2, len(report.coverage_matrix))
        self.assertEqual([], finding_codes(report))

    def test_missing_sibling_mechanism_blocks_family_claim(self):
        report = review_obligation_family_parity(
            (family(),),
            (evidence("material-reconcile", "material"),),
        )

        self.assertFalse(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_BLOCKED, report.confidence)
        self.assertIn("missing_family_member_mechanism_evidence", finding_codes(report))
        missing = [cell for cell in report.coverage_matrix if cell.member_id == "research"][0]
        self.assertEqual("missing", missing.status)

    def test_expected_member_inventory_is_independent_and_revisioned(self):
        report = review_obligation_family_parity(
            (
                family(
                    expected_member_ids=("material", "research", "current_node"),
                    inventory_revision="family:v2",
                    inventory_source_ref="preflight:packet-result:v2",
                    require_complete_inventory=True,
                    scoped_member_reasons={"current_node": "owned by a separately reviewed release surface"},
                ),
            ),
            (
                evidence("material-reconcile", "material"),
                evidence("research-reconcile", "research"),
            ),
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(("packet-result:current_node",), report.scoped_member_ids)
        self.assertEqual("family:v2", report.inventory_revisions["packet-result"])

    def test_omitted_expected_member_blocks_complete_family_claim(self):
        report = review_obligation_family_parity(
            (
                family(
                    expected_member_ids=("material", "research", "current_node"),
                    inventory_revision="family:v2",
                    inventory_source_ref="preflight:packet-result:v2",
                    require_complete_inventory=True,
                ),
            ),
            (
                evidence("material-reconcile", "material"),
                evidence("research-reconcile", "research"),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("expected_family_member_missing", finding_codes(report))
        self.assertEqual(("packet-result:current_node",), report.missing_member_ids)

    def test_family_evidence_must_bind_exact_member_obligations(self):
        report = review_obligation_family_parity(
            (family(),),
            (
                evidence(
                    "material-reconcile",
                    "material",
                    covered_obligations=("obligation:research",),
                ),
                evidence("research-reconcile", "research"),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("family_evidence_sibling_obligation_reference", finding_codes(report))
        material = [cell for cell in report.coverage_matrix if cell.member_id == "material"][0]
        self.assertEqual("invalid_provenance", material.status)

    def test_manual_event_cannot_prove_durable_reconciliation(self):
        report = review_obligation_family_parity(
            (family(),),
            (
                evidence("material-reconcile", "material"),
                evidence(
                    "research-manual-event",
                    "research",
                    provenance=FAMILY_EVIDENCE_PROVENANCE_MANUAL_EVENT,
                ),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("invalid_family_evidence_provenance", finding_codes(report))

    def test_exempt_member_does_not_require_evidence_but_stays_visible(self):
        report = review_obligation_family_parity(
            (
                family(
                    members=(
                        ObligationFamilyMember("material"),
                        ObligationFamilyMember(
                            "research",
                            required=False,
                            exception_reason="legacy route is explicitly out of scope",
                        ),
                    )
                ),
            ),
            (evidence("material-reconcile", "material"),),
        )

        self.assertTrue(report.ok)
        exempt = [cell for cell in report.coverage_matrix if cell.member_id == "research"][0]
        self.assertEqual("exempt", exempt.status)
        self.assertEqual(("legacy route is explicitly out of scope",), exempt.scoped_reasons)

    def test_same_class_bad_case_seed_derives_sibling_cases(self):
        cases = derive_same_class_bad_cases(
            family(
                members=(
                    ObligationFamilyMember("material"),
                    ObligationFamilyMember("research"),
                    ObligationFamilyMember("current_node"),
                )
            ),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
                source_case_id="material-case-1",
            ),
        )

        self.assertEqual(["research", "current_node"], [case.member_id for case in cases])
        self.assertTrue(all(case.source_case_id == "material-case-1" for case in cases))

    def test_bad_case_seed_carries_cartesian_model_backpropagation_fields(self):
        cases = derive_same_class_bad_cases(
            family(),
            FamilyBadCaseSeed(
                "observed-combination-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="old evidence consumed as current",
                affected_model_ids=("packet-router",),
                root_cause_dimension_ids=("packet.status", "evidence.path"),
                interaction_group_ids=("packet-evidence-contract",),
                observed_combination_case_id="cartesian:packet-router:packet-evidence-contract:1",
                generated_combination_case_ids=(
                    "cartesian:packet-router:packet-evidence-contract:1",
                    "cartesian:packet-router:packet-evidence-contract:2",
                ),
                coverage_receipt_ids=("contract_coverage:packet-router",),
            ),
        )

        self.assertEqual(("packet-router",), cases[0].affected_model_ids)
        self.assertEqual(("packet-evidence-contract",), cases[0].interaction_group_ids)
        self.assertEqual(
            "cartesian:packet-router:packet-evidence-contract:1",
            cases[0].observed_combination_case_id,
        )
        self.assertEqual(("contract_coverage:packet-router",), cases[0].coverage_receipt_ids)

    def test_analogous_defect_scan_blocks_unreviewed_must_scan_sibling(self):
        report = review_analogous_defect_scan(
            (family(),),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
            ),
        )

        self.assertFalse(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_BLOCKED, report.confidence)
        self.assertIn("unreviewed_analogous_defect_candidate", [finding.code for finding in report.findings])
        self.assertEqual(["research"], [candidate.member_id for candidate in report.candidates])

    def test_analogous_defect_scan_full_when_must_scan_sibling_is_covered(self):
        report = review_analogous_defect_scan(
            (family(),),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
            ),
            (
                AnalogousDefectCandidate(
                    "observed-material-miss:research:result_envelope_to_return_event:scan",
                    family_id="packet-result",
                    member_id="research",
                    mechanism_id="result_envelope_to_return_event",
                    failure_mode="joined_result_without_return_event",
                    disposition=ANALOGOUS_DISPOSITION_COVERED_CURRENT,
                    evidence_ids=("research-reconciliation-test",),
                ),
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_FULL, report.confidence)
        self.assertEqual([], [finding.code for finding in report.findings])

    def test_analogous_defect_scan_scopes_extra_radius_separate_change(self):
        report = review_analogous_defect_scan(
            (family(),),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
            ),
            (
                AnalogousDefectCandidate(
                    "observed-material-miss:research:result_envelope_to_return_event:scan",
                    family_id="packet-result",
                    member_id="research",
                    mechanism_id="result_envelope_to_return_event",
                    failure_mode="joined_result_without_return_event",
                    disposition=ANALOGOUS_DISPOSITION_COVERED_CURRENT,
                    evidence_ids=("research-reconciliation-test",),
                ),
                AnalogousDefectCandidate(
                    "receipt-ledger-related-surface",
                    family_id="receipt-ledger",
                    member_id="ack",
                    mechanism_id="durable_evidence_to_projection",
                    radius=ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN,
                    disposition=ANALOGOUS_DISPOSITION_SEPARATE_CHANGE,
                    disposition_reason="related evidence-projection surface tracked by separate model-miss change",
                ),
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn(
            "analogous_scan_candidate_scoped_to_separate_change",
            [finding.code for finding in report.findings],
        )

    def test_analogous_defect_scan_scopes_excluded_should_scan_without_blocking(self):
        report = review_analogous_defect_scan(
            (family(),),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
                exclude_member_ids=("research",),
            ),
            (
                AnalogousDefectCandidate(
                    "cache-projection-related-surface",
                    family_id="cache-projection",
                    member_id="warm-cache",
                    mechanism_id="durable_evidence_to_projection",
                    radius=ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN,
                    disposition=ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON,
                    disposition_reason="projection route cannot join packet results",
                ),
            ),
        )

        self.assertTrue(report.ok)
        self.assertEqual(FAMILY_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn(
            "analogous_scan_candidate_excluded_from_wider_radius",
            [finding.code for finding in report.findings],
        )

    def test_public_api_exports_helper(self):
        for name in (
            "ObligationFamily",
            "ObligationFamilyEvidence",
            "review_obligation_family_parity",
            "derive_same_class_bad_cases",
            "AnalogousDefectCandidate",
            "review_analogous_defect_scan",
        ):
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)


if __name__ == "__main__":
    unittest.main()
