# Hierarchical Model Mesh

Hierarchical model mesh is for FlowGuard projects where one model is becoming
too large, or several models now need a shared architecture review.

Use the plain mental model:

```text
Parent model = total map
Child model  = region map
Mesh review  = checks whether the region maps cover the total map without
               unsafe overlap or stale evidence
```

The mesh does not expand every child state graph. Each child remains responsible
for its own internal states and invariants. The parent boundary only reads the
child's contract and evidence summary.

Before the parent mesh trusts a child-model layout, it should record the target
split derivation from a FlowGuard source model or model-of-models. The
derivation names the source model, target child models, covered partition items,
state owner fields, side-effect owner fields, and rationale for the split. A
partition map without this derivation is not enough for green mesh confidence.

## When To Trigger It

Run a hierarchical mesh review when either quantity or scale suggests the model
architecture needs review:

- the project has three or more local FlowGuard models;
- one model has estimated or observed state count above the configured large
  model threshold, defaulting to `10_000`;
- a budgeted model group still has pending states and is incomplete;
- one model contains several unrelated functional areas;
- a legacy model is being reused as authority in a new parent/child hierarchy.

Quantity means coordination risk. Scale means split risk. Either one is enough
to ask the mesh whether the current model layout is still healthy.

## Partition Maps

## Target Split Derivation

Each parent boundary should include a `ModelTargetSplitDerivation`:

- `source_model_id`: the FlowGuard model used to derive the split;
- `target_child_model_ids`: child model regions in the target layout;
- `covered_partition_item_ids`: parent partition items covered by the split;
- `state_owner_fields` and `side_effect_owner_fields`: ownership boundaries
  that shaped the split;
- `rationale`: why this target layout follows from the model.

Missing source, missing target children, incomplete coverage, or prose-only
derivations block parent mesh confidence.

Each parent boundary should declare a partition map. A partition map names the
parent-space items and who owns them:

- functions;
- state fields;
- inputs and outputs;
- side effects;
- invariants;
- failure modes.

Ownership is explicit:

- `child`: one child owns this item;
- `parent`: the parent model owns this item;
- `read_only`: a child reads the item but does not own it;
- `shared_kernel`: a deliberately shared kernel owns the item.

A missing owner is a coverage gap. Two sibling owners for the same state write,
side effect, or functional area are overlap or ownership conflicts unless the
shared kernel is explicit.

## Large Model Review

Large model review is not automatic splitting. It asks what the next action
should be:

- `keep_as_single_model`: the large model is cohesive and evidence is complete;
- `split_into_children`: the model contains separable child areas;
- `merge_with_existing_model`: a candidate child overlaps an existing model;
- `continue_with_budgeted_execution_only`: keep the model for now, but do not
  report incomplete budgeted work as OK.

## Legacy Compatibility

Legacy models are not rewritten first. They are discovered and classified:

- `standalone_legacy`;
- `legacy_large_review_needed`;
- `legacy_candidate_parent`;
- `legacy_candidate_child`;
- `legacy_overlaps_existing`;
- `legacy_stale_or_partial`;
- `legacy_without_contract`.

A legacy model without a compatibility contract can be registered, but it should
not become strong child evidence. The compatibility contract records the
model's risk boundary, owned state, side effects, output contracts, freshness
rule, skipped checks, and evidence tier.

## Minimal API Example

```python
from flowguard import (
    ChildModelEvidence,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    ModelTargetSplitDerivation,
    review_hierarchical_mesh,
)

partition = HierarchyPartitionMap(
    parent_model_id="checkout_root",
    coverage_items=(
        HierarchyCoverageItem("payment", owner_model_id="payment"),
        HierarchyCoverageItem("inventory", owner_model_id="inventory"),
        HierarchyCoverageItem("order_status", ownership="parent"),
    ),
    child_models=(
        ChildModelEvidence("payment", evidence_tier="abstract_green"),
        ChildModelEvidence("inventory", evidence_tier="abstract_green"),
    ),
    target_split_derivation=ModelTargetSplitDerivation(
        "checkout_root",
        target_child_model_ids=("payment", "inventory"),
        covered_partition_item_ids=("payment", "inventory", "order_status"),
        rationale="derived from checkout model blocks and ownership boundaries",
    ),
)

report = review_hierarchical_mesh(partition)
assert report.ok
```

Run the full example:

```powershell
python examples/hierarchical_model_mesh/run_review.py
```
