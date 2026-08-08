import unittest

import flowguard
import flowguard.obligation_family as obligation_family_module
from flowguard import (
    FAMILY_CONFIDENCE_BLOCKED,
    FAMILY_CONFIDENCE_FULL,
    FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION,
    FAMILY_EVIDENCE_PROVENANCE_MANUAL_EVENT,
    FAMILY_EVIDENCE_STATUS_PASSED,
    ObligationFamily,
    ObligationFamilyEvidence,
    ObligationFamilyMember,
    FamilyBadCaseSeed,
    derive_same_class_bad_cases,
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
        self.assertEqual(
            [
                "observed-material-miss:research:result_envelope_to_return_event",
                "observed-material-miss:current_node:result_envelope_to_return_event",
            ],
            [case.case_id for case in cases],
        )

    def test_same_class_bad_case_generation_is_finite_and_declared(self):
        cases = derive_same_class_bad_cases(
            family(
                members=(
                    ObligationFamilyMember("material"),
                    ObligationFamilyMember("research"),
                    ObligationFamilyMember(
                        "optional_archive",
                        required=False,
                        exception_reason="archive is outside the current behavior claim",
                    ),
                    ObligationFamilyMember(
                        "different_mechanism",
                        required_mechanisms=("another_mechanism",),
                    ),
                )
            ),
            FamilyBadCaseSeed(
                "observed-material-miss",
                family_id="packet-result",
                source_member_id="material",
                mechanism_id="result_envelope_to_return_event",
                failure_mode="joined_result_without_return_event",
                exclude_member_ids=("research",),
            ),
        )

        self.assertEqual((), cases)

    def test_family_review_projects_declared_seed_without_second_scan_report(self):
        report = review_obligation_family_parity(
            (family(),),
            (
                evidence("material-reconcile", "material"),
                evidence("research-reconcile", "research"),
            ),
            (
                FamilyBadCaseSeed(
                    "observed-material-miss",
                    family_id="packet-result",
                    source_member_id="material",
                    mechanism_id="result_envelope_to_return_event",
                    failure_mode="joined_result_without_return_event",
                    source_case_id="material-case-1",
                ),
            ),
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(1, len(report.derived_bad_cases))
        self.assertEqual("research", report.derived_bad_cases[0].member_id)
        self.assertEqual("material-case-1", report.derived_bad_cases[0].source_case_id)

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

    def test_public_api_exports_only_family_and_finite_case_helpers(self):
        for name in (
            "ObligationFamily",
            "ObligationFamilyEvidence",
            "review_obligation_family_parity",
            "FamilyBadCaseSeed",
            "DerivedFamilyBadCase",
            "derive_same_class_bad_cases",
        ):
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)

        for retired_name in (
            "AnalogousDefectCandidate",
            "AnalogousDefectScanFinding",
            "AnalogousDefectScanReport",
            "review_analogous_defect_scan",
            "ANALOGOUS_SCAN_RADII",
            "ANALOGOUS_SCAN_DISPOSITIONS",
        ):
            self.assertNotIn(retired_name, flowguard.MODELING_HELPER_API)
            self.assertNotIn(retired_name, flowguard.__all__)
            self.assertFalse(hasattr(flowguard, retired_name), retired_name)
            self.assertNotIn(retired_name, obligation_family_module.__all__)
            self.assertFalse(hasattr(obligation_family_module, retired_name), retired_name)


if __name__ == "__main__":
    unittest.main()
