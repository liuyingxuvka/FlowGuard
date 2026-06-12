import unittest

from flowguard import (
    OBLIGATION_STATUS_RESOLVED,
    OBLIGATION_STATUS_SCOPED,
    RISK_CONFIDENCE_BLOCKED,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_GATE_ANALOGOUS_SCAN,
    RISK_GATE_ARTIFACT_PAYLOAD,
    RISK_GATE_DEFECT_FAMILY,
    RISK_GATE_FAMILY,
    RISK_GATE_MAINTENANCE_OBLIGATION,
    RISK_GATE_MODEL_ANGLE_REVIEW,
    RISK_GATE_MODEL_SPLIT,
    RISK_GATE_PARENT_MODEL_EVIDENCE,
    RISK_GATE_TEST_SPLIT,
    RISK_GATE_TOPOLOGY_HAZARD,
    RISK_GATE_MATLAB_CALLBACK_SEMANTICS,
    RISK_GATE_UI_DONE_CLAIM,
    RISK_GATE_UI_FUNCTIONAL_CHAIN,
    RISK_GATE_UI_IMPLEMENTATION,
    RISK_GATE_UI_REAL_SURFACE,
    RISK_LEDGER_DECISION_FULL,
    RISK_LEDGER_DECISION_SCOPED,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_FAILED,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_STALE,
    MaintenanceObligation,
    ProofArtifactRef,
    RiskEvidenceGate,
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


def proof_artifact(artifact_id="artifact:e1", *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status=RISK_PROOF_STATUS_PASSED,
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered or ("model:r1",),
    )


def gate(kind, evidence_id="", **kwargs):
    return RiskEvidenceGate(kind=kind, evidence_id=evidence_id, **kwargs)


def row(risk_id="r1", **kwargs):
    return RiskEvidenceRow(
        risk_id,
        model_obligation_id=kwargs.pop("model_obligation_id", "model:r1"),
        code_contract_id=kwargs.pop("code_contract_id", "code:r1"),
        proof_evidence_ids=kwargs.pop("proof_evidence_ids", ("e1",)),
        **kwargs,
    )


def obligation(obligation_id="obligation:structure", **kwargs):
    return MaintenanceObligation(
        obligation_id,
        owner_route=kwargs.pop("owner_route", "structure_mesh_maintenance"),
        reason_code=kwargs.pop("reason_code", "large_module"),
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

        missing_contract = review_risk_evidence_ledger(plan(rows=(row(code_contract_id=""),)))
        self.assertFalse(missing_contract.ok)
        self.assertEqual("missing_code_contract", missing_contract.decision)

    def test_missing_unknown_duplicate_and_parent_evidence_gaps_are_visible(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(
                    row("r1", proof_evidence_ids=("missing",)),
                    row(
                        "r1",
                        gates=(
                            gate(
                                RISK_GATE_PARENT_MODEL_EVIDENCE,
                                "parent:checkout",
                                current=False,
                            ),
                        ),
                    ),
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

    def test_old_flat_gate_fields_are_rejected_instead_of_fallback_accepted(self):
        for kwargs in (
            {"overclaims_full_confidence": True},
            {"defect_family_gate_required": True},
            {"defect_family_id": "defect-family:duplicate-submit"},
            {"family_gate_id": "family:submit"},
            {"model_split_gate_required": True},
            {"maintenance_obligations_required": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    row(**kwargs)

    def test_unknown_gate_kind_blocks(self):
        report = review_risk_evidence_ledger(plan(rows=(row(gates=(gate("old_field_name", "x"),)),)))

        self.assertFalse(report.ok)
        self.assertEqual("unknown_risk_gate_kind", report.decision)

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

    def test_required_defect_family_gate_must_be_named_and_current(self):
        missing = review_risk_evidence_ledger(plan(rows=(row(gates=(gate(RISK_GATE_DEFECT_FAMILY),)),)))
        self.assertFalse(missing.ok)
        self.assertEqual("missing_defect_family_gate", missing.decision)

        stale = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_DEFECT_FAMILY, "defect-family:duplicate-submit", current=False),)),))
        )
        self.assertFalse(stale.ok)
        self.assertEqual("defect_family_gate_not_current", stale.decision)

    def test_scoped_defect_family_gate_downgrades_final_confidence(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(
                    row(
                        gates=(
                            gate(
                                RISK_GATE_DEFECT_FAMILY,
                                "defect-family:duplicate-submit",
                                scoped_reasons=("release-only holdout deferred",),
                            ),
                        ),
                    ),
                )
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("defect_family_gate_scoped_confidence", finding_codes(report))

    def test_family_analogous_topology_and_angle_gates_share_one_shape(self):
        cases = (
            (RISK_GATE_FAMILY, "family:packet-result", "missing_family_gate", "family_gate_not_current", "family_gate_blocked"),
            (RISK_GATE_ANALOGOUS_SCAN, "analogous:packet-result", "missing_analogous_scan", "analogous_scan_not_current", "analogous_scan_blocked"),
            (RISK_GATE_TOPOLOGY_HAZARD, "topology:future-use", "missing_topology_hazard_review", "topology_hazard_review_not_current", "topology_hazard_review_blocked"),
            (RISK_GATE_MODEL_ANGLE_REVIEW, "model-angle:ai-route", "missing_model_angle_review", "model_angle_review_not_current", "model_angle_review_blocked"),
        )
        for kind, evidence_id, missing_code, stale_code, blocked_code in cases:
            with self.subTest(kind=kind, mode="missing"):
                missing = review_risk_evidence_ledger(plan(rows=(row(gates=(gate(kind),)),)))
                self.assertFalse(missing.ok)
                self.assertEqual(missing_code, missing.decision)

            with self.subTest(kind=kind, mode="stale"):
                stale = review_risk_evidence_ledger(plan(rows=(row(gates=(gate(kind, evidence_id, current=False),)),)))
                self.assertFalse(stale.ok)
                self.assertEqual(stale_code, stale.decision)

            with self.subTest(kind=kind, mode="blocked"):
                blocked = review_risk_evidence_ledger(
                    plan(rows=(row(gates=(gate(kind, evidence_id, confidence=RISK_CONFIDENCE_BLOCKED),)),))
                )
                self.assertFalse(blocked.ok)
                self.assertEqual(blocked_code, blocked.decision)

    def test_scoped_route_gate_downgrades_final_confidence(self):
        report = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_FAMILY, "family:packet-result", confidence=RISK_CONFIDENCE_SCOPED),)),))
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("family_gate_scoped_confidence", finding_codes(report))

    def test_required_model_and_test_split_gates_are_final_confidence_inputs(self):
        missing = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_MODEL_SPLIT), gate(RISK_GATE_TEST_SPLIT))),))
        )
        self.assertFalse(missing.ok)
        self.assertEqual("missing_model_split_gate", missing.decision)

        stale = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_MODEL_SPLIT, "modelmesh:search", current=False),)),))
        )
        self.assertFalse(stale.ok)
        self.assertEqual("model_split_gate_not_current", stale.decision)

    def test_ui_and_artifact_payload_gates_are_final_confidence_inputs(self):
        cases = (
            (
                RISK_GATE_UI_IMPLEMENTATION,
                "ui:click-through",
                "missing_ui_implementation_gate",
                "ui_implementation_gate_not_current",
                "ui_implementation_gate_blocked",
            ),
            (
                RISK_GATE_UI_REAL_SURFACE,
                "ui:observed-surface-inventory",
                "missing_ui_real_surface_gate",
                "ui_real_surface_gate_not_current",
                "ui_real_surface_gate_blocked",
            ),
            (
                RISK_GATE_UI_FUNCTIONAL_CHAIN,
                "ui:functional-chain",
                "missing_ui_functional_chain_gate",
                "ui_functional_chain_gate_not_current",
                "ui_functional_chain_gate_blocked",
            ),
            (
                RISK_GATE_UI_DONE_CLAIM,
                "ui:done-claim",
                "missing_ui_done_claim_gate",
                "ui_done_claim_gate_not_current",
                "ui_done_claim_gate_blocked",
            ),
            (
                RISK_GATE_MATLAB_CALLBACK_SEMANTICS,
                "ui:matlab-callback-baseline",
                "missing_matlab_callback_semantics_gate",
                "matlab_callback_semantics_gate_not_current",
                "matlab_callback_semantics_gate_blocked",
            ),
            (
                RISK_GATE_ARTIFACT_PAYLOAD,
                "payload:synthetic-pack",
                "missing_artifact_payload_gate",
                "artifact_payload_gate_not_current",
                "artifact_payload_gate_blocked",
            ),
        )
        for kind, evidence_id, missing_code, stale_code, blocked_code in cases:
            with self.subTest(kind=kind, mode="missing"):
                missing = review_risk_evidence_ledger(plan(rows=(row(gates=(gate(kind),)),)))
                self.assertFalse(missing.ok)
                self.assertEqual(missing_code, missing.decision)

            with self.subTest(kind=kind, mode="stale"):
                stale = review_risk_evidence_ledger(plan(rows=(row(gates=(gate(kind, evidence_id, current=False),)),)))
                self.assertFalse(stale.ok)
                self.assertEqual(stale_code, stale.decision)

            with self.subTest(kind=kind, mode="blocked"):
                blocked = review_risk_evidence_ledger(
                    plan(rows=(row(gates=(gate(kind, evidence_id, confidence=RISK_CONFIDENCE_BLOCKED),)),))
                )
                self.assertFalse(blocked.ok)
                self.assertEqual(blocked_code, blocked.decision)

    def test_scoped_test_split_gate_downgrades_final_confidence(self):
        report = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_TEST_SPLIT, "testmesh:full", confidence=RISK_CONFIDENCE_SCOPED),)),))
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("test_split_gate_scoped_confidence", finding_codes(report))

    def test_gate_dicts_are_coerced(self):
        report = review_risk_evidence_ledger(
            plan(rows=(row(gates=({"kind": RISK_GATE_FAMILY, "evidence_id": "family:submit"},)),))
        )

        self.assertTrue(report.ok, report.format_text())

    def test_strict_ledger_rejects_declaration_only_proof(self):
        report = review_risk_evidence_ledger(plan(require_proof_artifacts=True))

        self.assertFalse(report.ok)
        self.assertIn("missing_proof_evidence_artifact", finding_codes(report))

    def test_strict_ledger_accepts_artifact_backed_proof(self):
        report = review_risk_evidence_ledger(
            plan(
                require_proof_artifacts=True,
                proof_evidence=(proof(proof_artifact=proof_artifact()),),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_required_maintenance_obligation_must_be_named(self):
        report = review_risk_evidence_ledger(
            plan(rows=(row(gates=(gate(RISK_GATE_MAINTENANCE_OBLIGATION),)),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("missing_maintenance_obligation", report.decision)

    def test_open_maintenance_obligation_blocks_full_confidence(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(row(gates=(gate(RISK_GATE_MAINTENANCE_OBLIGATION, "obligation:structure"),)),),
                maintenance_obligations=(obligation(),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("open_maintenance_obligation", report.decision)

    def test_resolved_maintenance_obligation_needs_resolution_evidence(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(row(maintenance_obligation_ids=("obligation:structure",)),),
                maintenance_obligations=(obligation(status=OBLIGATION_STATUS_RESOLVED),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("maintenance_obligation_missing_resolution_evidence", report.decision)

    def test_resolved_maintenance_obligation_with_evidence_allows_full_claim(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(row(gates=(gate(RISK_GATE_MAINTENANCE_OBLIGATION, "obligation:structure"),)),),
                maintenance_obligations=(
                    obligation(
                        status=OBLIGATION_STATUS_RESOLVED,
                        evidence_ids=("structuremesh:passed",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RISK_LEDGER_DECISION_FULL, report.decision)

    def test_bug_repair_row_can_require_family_analogous_and_maintenance_links(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(
                    row(
                        "bug:duplicate-submit",
                        gates=(
                            gate(RISK_GATE_DEFECT_FAMILY, "defect-family:duplicate-submit"),
                            gate(RISK_GATE_FAMILY, "family:submit-repair"),
                            gate(RISK_GATE_ANALOGOUS_SCAN, "analogous:submit-repair"),
                            gate(RISK_GATE_MAINTENANCE_OBLIGATION, "obligation:structure"),
                        ),
                    ),
                ),
                maintenance_obligations=(
                    obligation(
                        status=OBLIGATION_STATUS_RESOLVED,
                        evidence_ids=("structuremesh:passed",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RISK_LEDGER_DECISION_FULL, report.decision)

    def test_scoped_maintenance_obligation_downgrades_confidence(self):
        report = review_risk_evidence_ledger(
            plan(
                rows=(row(maintenance_obligation_ids=("obligation:structure",)),),
                maintenance_obligations=(
                    obligation(
                        status=OBLIGATION_STATUS_SCOPED,
                        scope_reason="secondary entrypoint is release-only",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(RISK_LEDGER_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("maintenance_obligation_scoped_confidence", finding_codes(report))


if __name__ == "__main__":
    unittest.main()
