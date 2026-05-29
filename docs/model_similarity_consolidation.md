# Model Similarity Consolidation

Model Similarity Consolidation compares structured FlowGuard model signatures
before a project creates another model boundary or extracts shared code.

Use it when several features look like variants of the same workflow, when a
new model may overlap an existing one, or when similar model-backed code might
be consolidated. The review returns typed relations and downstream route
handoffs. It does not merge models or rewrite production code.

## What It Compares

Each `ModelSignature` can name:

- model id, path, workflow family, and variant id;
- FunctionBlocks, inputs, outputs, state owners, state reads, and side effects;
- invariants, failure modes, input/output contracts, and public entrypoints;
- parent/child model ids, evidence ids, freshness, blindspots, and known false
  friends.

The review compares these fields structurally instead of relying on raw source
text or name similarity.

## Relation Types

The review can classify:

- `same_workflow`
- `same_family_variant`
- `symmetric_flow`
- `shared_kernel_candidate`
- `duplicate_boundary`
- `overlapping_ownership`
- `parent_child_candidate`
- `sibling_overlap`
- `adapter_only_difference`
- `evidence_duplicate`
- `false_friend`
- `unrelated`
- `manual_review`

Each relation records matched elements, different elements, risk if merged,
risk if kept separate, recommendation, required next route, required evidence,
and rationale.

## Route Handoffs

Similarity findings are handoffs:

- same workflow -> Existing Model Preflight reuse or extension;
- family variant -> ModelMesh and Model-Test Alignment;
- shared kernel or symmetric flow -> Code Structure Recommendation and
  ModelMesh;
- duplicate boundary or adapter-only difference -> Architecture Reduction;
- parent/child or sibling overlap -> ModelMesh;
- evidence duplicate -> Model-Test Alignment;
- false friend -> keep separate and preserve the rationale.

The downstream route owns implementation confidence. Similarity alone is not
proof that code can be changed.

## Example

```python
from flowguard import (
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    review_model_similarity_consolidation,
)

plan = ModelSimilarityPlan(
    "checkout-similarity",
    signatures=(
        ModelSignature(
            "checkout-simple",
            workflow_family="checkout",
            variant_id="simple",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            failure_modes=("duplicate_submit",),
            evidence_ids=("sim:checkout-family",),
        ),
        ModelSignature(
            "checkout-retry",
            workflow_family="checkout",
            variant_id="retry",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            failure_modes=("duplicate_submit",),
            evidence_ids=("sim:checkout-family",),
        ),
    ),
    comparison_pairs=(("checkout-simple", "checkout-retry"),),
    evidence=(ModelSimilarityEvidence("sim:checkout-family"),),
    require_current_evidence=True,
)

report = review_model_similarity_consolidation(plan)
print(report.format_text())
```

For a runnable scaffold:

```powershell
python -m flowguard model-similarity-template --output .
python .flowguard/model_similarity_consolidation/run_checks.py
```

## Limits

- A relation can be scoped when evidence is missing or stale.
- `false_friend` relations intentionally block consolidation advice.
- Public entrypoint changes still need StructureMesh or conformance evidence.
- Family claims still need Model-Test Alignment and obligation-family evidence
  when tests or code contracts are in scope.
