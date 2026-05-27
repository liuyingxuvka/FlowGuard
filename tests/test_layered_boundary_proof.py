import unittest

from flowguard import (
    ChildProofContract,
    ChildReattachmentProof,
    LeafBoundaryMatrix,
    LeafBoundaryMatrixCell,
    LayeredBoundaryProofPlan,
    LAYERED_PROOF_STATUS_PROGRESS_ONLY,
    ParentCoverageItem,
    ProofArtifactRef,
    review_layered_boundary_proof,
)


def cell(**overrides):
    data = {
        "cell_id": "submit.empty:idle",
        "input_case": "submit.empty",
        "state_case": "idle",
        "expected_outputs": ("Rejected",),
        "observed_outputs": ("Rejected",),
        "expected_next_states": ("idle",),
        "observed_next_states": ("idle",),
        "expected_state_writes": (),
        "observed_state_writes": (),
        "expected_side_effects": (),
        "observed_side_effects": (),
        "expected_error_paths": ("ValueError",),
        "observed_error_paths": ("ValueError",),
        "evidence_ids": ("test:reject-empty",),
    }
    data.update(overrides)
    return LeafBoundaryMatrixCell(**data)


def proof_artifact(artifact_id="proof:validate-submit", *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status="passed",
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered or ("validate-submit",),
    )


def child(**overrides):
    data = {
        "child_model_id": "validate-submit",
        "evidence_id": "validate-submit:v1",
        "responsibilities": ("validate-submit",),
        "functions_owned": ("validate",),
        "inputs_accepted": ("submit.empty", "submit.valid"),
        "outputs_emitted": ("Rejected", "Accepted"),
        "state_owned": ("seen_ids",),
        "side_effects_owned": (),
        "invariants_owned": ("valid-submit-only",),
        "risk_classes": ("invalid-input",),
        "contracts_out": ("submit.validation",),
        "is_leaf": True,
    }
    data.update(overrides)
    return ChildProofContract(**data)


def reattachment(**overrides):
    data = {
        "child_model_id": "validate-submit",
        "consumed_evidence_id": "validate-submit:v1",
        "expected_inputs": ("submit.empty", "submit.valid"),
        "expected_outputs": ("Rejected", "Accepted"),
        "expected_state_owned": ("seen_ids",),
        "expected_contracts_out": ("submit.validation",),
    }
    data.update(overrides)
    return ChildReattachmentProof(**data)


def matrix(**overrides):
    data = {
        "leaf_model_id": "validate-submit",
        "matrix_id": "validate-submit:matrix:v1",
        "expected_cell_ids": ("submit.empty:idle",),
        "cells": (cell(),),
    }
    data.update(overrides)
    return LeafBoundaryMatrix(**data)


def plan(**overrides):
    data = {
        "proof_id": "checkout-layered-proof",
        "parent_model_id": "checkout",
        "parent_items": (
            ParentCoverageItem("validate-submit", owner_model_id="validate-submit"),
        ),
        "child_contracts": (child(),),
        "reattachment_proofs": (reattachment(),),
        "leaf_matrices": (matrix(),),
    }
    data.update(overrides)
    return LayeredBoundaryProofPlan(**data)


def codes(report):
    return {finding.code for finding in report.findings}


class LayeredBoundaryProofTests(unittest.TestCase):
    def test_green_layered_proof_can_continue(self):
        report = review_layered_boundary_proof(plan())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("layered_boundary_proof_green", report.decision)
        self.assertIn("flowguard layered boundary proof", report.format_text())

    def test_parent_coverage_gap_blocks(self):
        report = review_layered_boundary_proof(
            plan(parent_items=(ParentCoverageItem("validate-submit"),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("parent_coverage_gap_blocked", report.decision)
        self.assertIn("parent_coverage_gap", codes(report))

    def test_illegal_child_overlap_blocks(self):
        second = child(
            child_model_id="normalize-submit",
            evidence_id="normalize-submit:v1",
            responsibilities=("normalize-submit",),
            functions_owned=("validate",),
            inputs_accepted=("submit.valid",),
            outputs_emitted=("Normalized",),
            state_owned=(),
            invariants_owned=("normalized-submit-only",),
            risk_classes=("normalization",),
            contracts_out=("submit.normalized",),
            is_leaf=False,
        )
        report = review_layered_boundary_proof(
            plan(
                parent_items=(
                    ParentCoverageItem("validate-submit", owner_model_id="validate-submit"),
                    ParentCoverageItem("normalize-submit", owner_model_id="normalize-submit"),
                ),
                child_contracts=(child(), second),
                reattachment_proofs=(
                    reattachment(),
                    ChildReattachmentProof(
                        "normalize-submit",
                        consumed_evidence_id="normalize-submit:v1",
                        expected_outputs=("Normalized",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("child_disjointness_blocked", report.decision)
        self.assertIn("child_overlap_function", codes(report))

    def test_stale_reattachment_blocks_parent_confidence(self):
        report = review_layered_boundary_proof(
            plan(reattachment_proofs=(reattachment(consumed_evidence_id="validate-submit:old"),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("child_reattachment_required", report.decision)
        self.assertIn("child_reattachment_stale_evidence", codes(report))

    def test_missing_leaf_cell_blocks_matrix_confidence(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(expected_cell_ids=("submit.empty:idle", "submit.valid:idle")),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_boundary_matrix_required", report.decision)
        self.assertIn("leaf_matrix_missing_cell", codes(report))

    def test_leaf_matrix_must_match_cartesian_axes(self):
        report = review_layered_boundary_proof(
            plan(
                leaf_matrices=(
                    matrix(
                        input_cases=("submit.empty", "submit.valid"),
                        state_cases=("idle",),
                        expected_cell_ids=("submit.empty:idle",),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_boundary_matrix_required", report.decision)
        self.assertIn("leaf_matrix_not_cartesian", codes(report))

    def test_unexpected_leaf_cell_blocks_matrix_confidence(self):
        report = review_layered_boundary_proof(
            plan(
                leaf_matrices=(
                    matrix(
                        expected_cell_ids=("submit.empty:idle",),
                        cells=(cell(), cell(cell_id="submit.valid:idle", input_case="submit.valid")),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_boundary_matrix_required", report.decision)
        self.assertIn("leaf_matrix_unexpected_cell", codes(report))

    def test_leaf_underflow_blocks_when_declared_behavior_is_missing(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(cells=(cell(observed_outputs=()),)),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_boundary_underflow", report.decision)
        self.assertIn("leaf_cell_missing_output", codes(report))

    def test_leaf_output_overflow_blocks(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(cells=(cell(observed_outputs=("Rejected", "Accepted")),)),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_boundary_overflow", report.decision)
        self.assertIn("leaf_cell_extra_output", codes(report))

    def test_too_large_leaf_requires_split(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(too_large_for_leaf=True, split_required=True),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_split_required", report.decision)
        self.assertIn("leaf_split_required", codes(report))

    def test_progress_only_cell_is_not_pass_evidence(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(cells=(cell(evidence_status=LAYERED_PROOF_STATUS_PROGRESS_ONLY),)),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_evidence_not_current", report.decision)
        self.assertIn("leaf_cell_evidence_not_current_pass", codes(report))

    def test_internal_path_cell_evidence_is_not_leaf_boundary_proof(self):
        report = review_layered_boundary_proof(
            plan(leaf_matrices=(matrix(cells=(cell(assertion_scope="internal_path"),)),))
        )

        self.assertFalse(report.ok)
        self.assertEqual("leaf_evidence_not_current", report.decision)
        self.assertIn("leaf_cell_internal_path_only", codes(report))

    def test_strict_layered_proof_rejects_declaration_only_evidence(self):
        report = review_layered_boundary_proof(plan(require_proof_artifacts=True))

        self.assertFalse(report.ok)
        self.assertIn("child_missing_proof_artifact", codes(report))
        self.assertIn("leaf_cell_missing_proof_artifact", codes(report))

    def test_strict_layered_proof_accepts_artifact_backed_evidence(self):
        backed_child = child(proof_artifact=proof_artifact("proof:child", "validate-submit"))
        backed_cell = cell(proof_artifact=proof_artifact("proof:cell", "test:reject-empty"))
        report = review_layered_boundary_proof(
            plan(
                require_proof_artifacts=True,
                child_contracts=(backed_child,),
                leaf_matrices=(matrix(cells=(backed_cell,)),),
            )
        )

        self.assertTrue(report.ok, report.format_text())


if __name__ == "__main__":
    unittest.main()
