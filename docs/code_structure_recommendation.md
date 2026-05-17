# Code Structure Recommendation

Code Structure Recommendation is FlowGuard's helper layer for turning a
functional model into a recommended implementation structure before production
code is written. It is a parallel route beside ordinary model-first work, not a
hard gate for every model.

## Use Cases

Use it when:

- a user asks for an architecture or file-split recommendation;
- a FlowGuard functional model already exists and implementation structure is
  unclear;
- a planned feature has enough state, side effects, public entrypoints,
  retries, caches, or deduplication behavior that a monolithic script is
  likely;
- a hierarchical functional model should guide parent/child code boundaries.

## Public API

The main objects are:

- `TargetModuleRecommendation`: one proposed target module or script with
  owned FunctionBlocks, state fields, side effects, config, public entrypoints,
  validation boundaries, and rationale.
- `CodeStructureRecommendation`: the complete recommendation, including source
  FlowGuard model evidence, target modules, owner maps, facade plan, validation
  boundaries, and rationale.
- `CodeStructureRecommendationReport`: structured review output.
- `review_code_structure_recommendation(recommendation)`: the executable
  checker.

## Relationship To StructureMesh

Code Structure Recommendation handles direct no-code or pre-code architecture
requests. StructureMesh remains scoped to existing large scripts, modules,
packages, command surfaces, or API surfaces being split.

When StructureMesh reviews an existing large code split, model-derived target
structure is not optional. The `StructureMeshPlan` includes a
`CodeStructureRecommendation`, and `review_structure_mesh(...)` checks that the
target recommendation aligns with partition owners, child modules, facades,
state owners, side-effect owners, and validation boundaries.

## Example

```python
from flowguard import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


recommendation = CodeStructureRecommendation(
    "checkout-target-structure",
    source_model_id="checkout-functional-model",
    parent_module_id="checkout",
    target_modules=(
        TargetModuleRecommendation(
            "orchestrator",
            owns_function_blocks=("RouteCheckout",),
            rationale="orchestration owns ordering but not durable writes",
        ),
        TargetModuleRecommendation(
            "effects",
            owns_function_blocks=("PersistOrder",),
            owns_side_effects=("write_order",),
            rationale="durable writes stay behind an adapter",
        ),
    ),
    function_block_map=(
        ("RouteCheckout", "orchestrator"),
        ("PersistOrder", "effects"),
    ),
    side_effect_owner_map=(("write_order", "effects"),),
    validation_boundaries=("model scenario replay",),
    rationale="the model separates ordering from durable effects",
)

report = review_code_structure_recommendation(recommendation)
print(report.format_text())
```

For a ready scaffold, run:

```powershell
python -m flowguard code-structure-recommendation-template --output .
```
