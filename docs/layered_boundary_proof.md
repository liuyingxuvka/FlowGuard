# Layered Boundary Proof

Layered boundary proof connects ModelMesh, Model-Test Alignment, and TestMesh
evidence into one parent confidence boundary.

It checks four tables:

1. Parent coverage: every parent responsibility has a child, parent, read-only,
   shared-kernel, bridge, or explicit out-of-scope owner.
2. Child disjointness: child models do not illegally overlap on functions,
   state, side effects, invariants, risk classes, or parent responsibilities.
3. Child reattachment: the parent consumes each child's current evidence id and
   the expected input/output/state/side-effect/contract handoff.
4. Leaf boundary matrix: leaf models prove every finite
   `Input x State -> Set(Output x State)` cell against real-code evidence.

When the parent proof depends on generated bad cases from fields, payloads,
same-class families, transition cells, or mesh closure hazards, use
ContractExhaustionMesh to create the canonical case ids first. Layered boundary
proof consumes those ids through child contracts, reattachment proof, leaf
matrix evidence, Model-Test Alignment, and TestMesh; it does not generate a
parallel list of analogous cases.

When a leaf matrix declares `input_cases` and `state_cases`, FlowGuard treats
their Cartesian product as the expected finite boundary. Missing cells,
unexpected cells, missing observed outputs/states/writes/effects/errors, extra
observed behavior, stale evidence, and internal-path-only evidence all block
parent confidence.

Leaf cells can also declare `runtime_node_ids` and
`runtime_path_evidence_ids`. Use these when a finite `Input x State` cell must
prove that real code reached the matching FlowGuard node, not merely that a
test asserted an output. A cell that names runtime nodes without runtime path
evidence stays blocked.

Use `review_layered_boundary_proof(...)` after project-specific adapters have
collected the rows. The helper does not run tests or inspect source. It reviews
the structured evidence and blocks parent confidence for gaps, illegal overlap,
stale reattachment, missing leaf cells, overflowed outputs, progress-only
evidence, or leaves that are too large and need another split.

For parent confidence, prefer `require_proof_artifacts=True`. In that mode,
child contracts and leaf cells cannot be supported by declaration-only
`passed/current` rows. Each row needs a `ProofArtifactRef` with a result path,
artifact fingerprint, passing status, current route evidence, matching covered
obligations, and external-contract scope.

```python
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

plan = LayeredBoundaryProofPlan(
    "checkout-layered-proof",
    "checkout-parent",
    require_proof_artifacts=True,
    parent_items=(ParentCoverageItem("validate-submit", owner_model_id="validate"),),
    child_contracts=(
        ChildProofContract(
            "validate",
            evidence_id="validate:v1",
            responsibilities=("validate-submit",),
            inputs_accepted=("empty-submit",),
            outputs_emitted=("Rejected",),
            is_leaf=True,
            proof_artifact=ProofArtifactRef(
                "artifact:validate-child",
                result_status="passed",
                exit_code=0,
                result_path="tmp/validate-child.json",
                artifact_fingerprints={"tmp/validate-child.json": "sha256:..."},
                covered_obligation_ids=("validate-submit",),
            ),
        ),
    ),
    reattachment_proofs=(
        ChildReattachmentProof(
            "validate",
            consumed_evidence_id="validate:v1",
            expected_inputs=("empty-submit",),
            expected_outputs=("Rejected",),
        ),
    ),
    leaf_matrices=(
        LeafBoundaryMatrix(
            "validate",
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
                    evidence_ids=("test:reject-empty",),
                    proof_artifact=ProofArtifactRef(
                        "artifact:reject-empty-cell",
                        result_status="passed",
                        exit_code=0,
                        result_path="tmp/reject-empty-cell.json",
                        artifact_fingerprints={"tmp/reject-empty-cell.json": "sha256:..."},
                        covered_obligation_ids=("test:reject-empty",),
                    ),
                ),
            ),
        ),
    ),
)

report = review_layered_boundary_proof(plan)
assert report.ok
```

Generate a project scaffold with:

```powershell
python -m flowguard layered-boundary-proof-template --output .
```
