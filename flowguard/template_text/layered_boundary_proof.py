"""Template text for FlowGuard layered boundary proof route."""

from __future__ import annotations

LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a parent model is fully covered by child models, child boundaries are disjoint, child evidence reattaches to the parent, and leaf code boundaries have complete finite Input x State coverage.
Guards against: parent coverage gaps, illegal child overlap, stale child evidence, coarse leaf models, and happy-path-only boundary testing.
Use before editing: Run this before claiming parent model, full-system, release, or done confidence from a parent/child FlowGuard model tree.
Run: python .flowguard/layered_boundary_proof/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    ChildProofContract,
    ChildReattachmentProof,
    LeafBoundaryMatrix,
    LeafBoundaryMatrixCell,
    LayeredBoundaryProofPlan,
    ParentCoverageItem,
    ProofArtifactRef,
    review_layered_boundary_proof,
)


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{artifact_id.replace(':', '_')}.json"
    return ProofArtifactRef(
        artifact_id,
        result_status="passed",
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def correct_layered_proof() -> LayeredBoundaryProofPlan:
    return LayeredBoundaryProofPlan(
        "checkout-layered-boundary-proof",
        "checkout-parent",
        require_proof_artifacts=True,
        parent_items=(
            ParentCoverageItem("validate-submit", owner_model_id="validate-submit"),
        ),
        child_contracts=(
            ChildProofContract(
                "validate-submit",
                evidence_id="validate-submit:v1",
                responsibilities=("validate-submit",),
                functions_owned=("validate_submit",),
                inputs_accepted=("empty-submit", "valid-submit"),
                outputs_emitted=("Rejected", "Accepted"),
                state_owned=("seen_ids",),
                contracts_out=("submit-validation",),
                is_leaf=True,
                proof_artifact=proof_artifact("artifact:validate-submit-child", "validate-submit"),
            ),
        ),
        reattachment_proofs=(
            ChildReattachmentProof(
                "validate-submit",
                consumed_evidence_id="validate-submit:v1",
                expected_inputs=("empty-submit", "valid-submit"),
                expected_outputs=("Rejected", "Accepted"),
                expected_state_owned=("seen_ids",),
                expected_contracts_out=("submit-validation",),
            ),
        ),
        leaf_matrices=(
            LeafBoundaryMatrix(
                "validate-submit",
                matrix_id="validate-submit:matrix:v1",
                input_cases=("empty-submit",),
                state_cases=("idle",),
                expected_cell_ids=("empty-submit:idle",),
                cells=(
                    LeafBoundaryMatrixCell(
                        "empty-submit:idle",
                        "empty-submit",
                        "idle",
                        expected_outputs=("Rejected",),
                        observed_outputs=("Rejected",),
                        expected_next_states=("idle",),
                        observed_next_states=("idle",),
                        expected_error_paths=("ValueError",),
                        observed_error_paths=("ValueError",),
                        evidence_ids=("test:reject-empty-submit",),
                        proof_artifact=proof_artifact(
                            "artifact:reject-empty-submit-cell",
                            "test:reject-empty-submit",
                        ),
                    ),
                ),
            ),
        ),
    )


def broken_layered_proof() -> LayeredBoundaryProofPlan:
    return LayeredBoundaryProofPlan(
        "broken-checkout-layered-boundary-proof",
        "checkout-parent",
        parent_items=(
            ParentCoverageItem("validate-submit"),
        ),
        child_contracts=(
            ChildProofContract(
                "validate-submit",
                evidence_id="validate-submit:v2",
                responsibilities=("validate-submit",),
                functions_owned=("validate_submit",),
                inputs_accepted=("empty-submit", "valid-submit"),
                outputs_emitted=("Rejected", "Accepted"),
                state_owned=("seen_ids",),
                contracts_out=("submit-validation",),
                is_leaf=True,
            ),
        ),
        reattachment_proofs=(
            ChildReattachmentProof(
                "validate-submit",
                consumed_evidence_id="validate-submit:v1",
                expected_inputs=("empty-submit", "valid-submit"),
                expected_outputs=("Rejected", "Accepted"),
                expected_state_owned=("seen_ids",),
                expected_contracts_out=("submit-validation",),
            ),
        ),
        leaf_matrices=(
            LeafBoundaryMatrix(
                "validate-submit",
                matrix_id="validate-submit:matrix:v2",
                input_cases=("empty-submit", "valid-submit"),
                state_cases=("idle",),
                expected_cell_ids=("empty-submit:idle", "valid-submit:idle"),
                cells=(
                    LeafBoundaryMatrixCell(
                        "empty-submit:idle",
                        "empty-submit",
                        "idle",
                        expected_outputs=("Rejected",),
                        observed_outputs=("Rejected", "Accepted"),
                        expected_next_states=("idle",),
                        observed_next_states=("idle",),
                        evidence_ids=("test:reject-empty-submit",),
                    ),
                ),
            ),
        ),
    )


def run_checks():
    return (
        review_layered_boundary_proof(correct_layered_proof()),
        review_layered_boundary_proof(broken_layered_proof()),
    )
'''

LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE = '''"""Run the Layered Boundary Proof template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE = """# FlowGuard Layered Boundary Proof Notes

Use this scaffold when a FlowGuard model tree needs a parent-to-leaf proof
chain.

## The Four Tables

- Parent coverage: every parent responsibility is owned by a child, parent,
  read-only boundary, shared kernel, bridge, or explicit out-of-scope
  disposition.
- Child disjointness: child models do not illegally share functions, state,
  side effects, invariants, risk classes, or responsibilities.
- Child reattachment: the parent consumes each child's current evidence id and
  only the inputs, outputs, state owners, side effects, and contracts that the
  parent is allowed to consume.
- Leaf boundary matrix: each leaf model has complete finite
  `Input x State -> Set(Output x State)` evidence, including next states, state
  writes, side effects, and error paths.
- When input and state axes are declared, the expected cells must equal their
  Cartesian product; unexpected cells or missing observed behavior are blockers.

If a leaf matrix is too large, split the model further or record an explicit
scoped exemption. Progress-only, skipped, stale, or release-only evidence is
not a green proof.
"""

__all__ = [
    'LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE',
    'LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE',
    'LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE',
]
