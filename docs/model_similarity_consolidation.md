# Model Similarity Consolidation

Model Similarity Consolidation compares structured FlowGuard model signatures
before a project creates another model boundary, changes one member of a
similar feature family, or extracts shared code.

Use it when several features look like variants of the same workflow, when a
new model may overlap an existing one, or when similar model-backed code might
be consolidated. The review returns typed relations, maintenance groups,
change-impact obligations, shared and variant test obligations, code
maintenance obligations, and downstream route handoffs. It does not merge
models or rewrite production code.

## What It Compares

Each `ModelSignature` can name:

- model id, path, workflow family, and variant id;
- FunctionBlocks, inputs, outputs, state owners, state reads, and side effects;
- invariants, failure modes, input/output contracts, and public entrypoints;
- code paths, test paths, public behaviors, shared-kernel id, adapters,
  maintenance tags, and changed references;
- parent/child model ids, evidence ids, freshness, blindspots, and known false
  friends.

The review compares these fields structurally instead of relying on raw source
text or name similarity.

## Basic Path

For ordinary maintenance work, start with the profile helpers and pass the
single handoff to downstream routes:

```python
from flowguard import (
    model_signature_maintenance,
    model_similarity_plan_for_changed_member,
    review_model_similarity_consolidation,
)

signatures = (
    model_signature_maintenance(
        "checkout-simple",
        workflow_family="checkout",
        variant_id="simple",
        function_blocks=("ValidateOrder",),
        code_paths=("flowguard/checkout/simple.py",),
        test_paths=("tests/test_checkout_simple.py",),
        shared_kernel_id="checkout_core",
        adapter_ids=("simple_adapter",),
    ),
    model_signature_maintenance(
        "checkout-retry",
        workflow_family="checkout",
        variant_id="retry",
        function_blocks=("ValidateOrder",),
        code_paths=("flowguard/checkout/retry.py",),
        test_paths=("tests/test_checkout_retry.py",),
        shared_kernel_id="checkout_core",
        adapter_ids=("retry_adapter",),
    ),
)

plan = model_similarity_plan_for_changed_member(
    "checkout-similarity",
    signatures,
    changed_model_id="checkout-simple",
)
report = review_model_similarity_consolidation(plan)
handoff = report.to_handoff()
```

Use `handoff` on Existing Model Preflight, Code Structure Recommendation,
Model-Test Alignment, or Architecture Reduction. Do not copy relation ids,
maintenance-group ids, test-obligation ids, and code-obligation ids into
separate downstream fields.

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

## Maintenance Output

The same review also turns relation evidence into software-maintenance output:

- `maintenance_groups`: A/B/C model ids that must be maintained together, plus
  their code paths, test paths, shared elements, variant elements, relation ids,
  shared-kernel ids, adapters, and downstream routes.
- `change_impacts`: when `changed_model_ids` or `changed_code_paths` are
  provided, the report names sibling models and their code/test paths that must
  be checked before claiming the change covered the whole family.
- `test_obligations`: shared behaviors need shared tests across the family;
  variant behavior needs per-member tests.
- `code_obligations`: shared-kernel, adapter, duplicate-boundary,
  ownership-overlap, and false-friend quarantine obligations for downstream
  Code Structure Recommendation, Architecture Reduction, or ModelMesh review.

This is the intended answer to the maintenance problem where feature A is
fixed while similar feature B or C is forgotten.

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

## Full Schema Path

Use full dataclasses when a review needs explicit comparison pairs, current
evidence rows, false-friend declarations, or detailed metadata:

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
            code_paths=("flowguard/checkout/simple.py",),
            test_paths=("tests/test_checkout_simple.py",),
            shared_kernel_id="checkout_core",
            adapter_ids=("simple_adapter",),
            evidence_ids=("sim:checkout-family",),
        ),
        ModelSignature(
            "checkout-retry",
            workflow_family="checkout",
            variant_id="retry",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            failure_modes=("duplicate_submit",),
            code_paths=("flowguard/checkout/retry.py",),
            test_paths=("tests/test_checkout_retry.py",),
            shared_kernel_id="checkout_core",
            adapter_ids=("retry_adapter",),
            evidence_ids=("sim:checkout-family",),
        ),
    ),
    comparison_pairs=(("checkout-simple", "checkout-retry"),),
    changed_model_ids=("checkout-simple",),
    evidence=(ModelSimilarityEvidence("sim:checkout-family"),),
    require_current_evidence=True,
)

report = review_model_similarity_consolidation(plan)
handoff = report.to_handoff()
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
- False friends are quarantined out of maintenance groups.
- Public entrypoint changes still need StructureMesh or conformance evidence.
- Family claims still need Model-Test Alignment and obligation-family evidence
  when tests or code contracts are in scope.
- Similarity can name sibling review obligations, but the downstream route
  still owns proof that code or tests were changed safely.
