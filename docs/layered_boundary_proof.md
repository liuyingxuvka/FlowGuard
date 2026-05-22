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

Use `review_layered_boundary_proof(...)` after project-specific adapters have
collected the rows. The helper does not run tests or inspect source. It reviews
the structured evidence and blocks parent confidence for gaps, illegal overlap,
stale reattachment, missing leaf cells, overflowed outputs, progress-only
evidence, or leaves that are too large and need another split.

```python
from flowguard import (
    ChildProofContract,
    ChildReattachmentProof,
    LeafBoundaryMatrix,
    LeafBoundaryMatrixCell,
    LayeredBoundaryProofPlan,
    ParentCoverageItem,
    review_layered_boundary_proof,
)

plan = LayeredBoundaryProofPlan(
    "checkout-layered-proof",
    "checkout-parent",
    parent_items=(ParentCoverageItem("validate-submit", owner_model_id="validate"),),
    child_contracts=(
        ChildProofContract(
            "validate",
            evidence_id="validate:v1",
            responsibilities=("validate-submit",),
            inputs_accepted=("empty-submit",),
            outputs_emitted=("Rejected",),
            is_leaf=True,
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
            expected_cell_ids=("empty-submit:idle",),
            cells=(
                LeafBoundaryMatrixCell(
                    "empty-submit:idle",
                    "empty-submit",
                    "idle",
                    expected_outputs=("Rejected",),
                    observed_outputs=("Rejected",),
                    evidence_ids=("test:reject-empty",),
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
