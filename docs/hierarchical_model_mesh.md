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

When parent confidence also claims that the underlying code stays inside model
boundaries, add layered boundary proof. The parent checks coverage and child
disjointness, consumes current child reattachment evidence, and requires every
lowest leaf model to prove a complete finite
`Input x State -> Set(Output x State)` matrix against real-code evidence. A
child-local green model result alone does not prove that leaf code boundary.

For whole-flow parent confidence, the parent boundary also needs a closure
model. The closure model is a small FlowGuard-style model of the model network:
root entries, child-output tokens, parent or sibling consumers, required joins,
normal/failure exits, and explicit out-of-scope dispositions. It proves the
handoffs close without expanding child internals.

If a child model was changed to repair a bug, its own green result is not enough
for parent confidence. The parent must reattach that child by consuming the
current child evidence id and checking that the child still accepts the expected
inputs, emits the expected outputs, owns the expected state and side effects,
and provides the outgoing guarantees the parent flow depends on.

Keep the bug instance and the bug class separate. Model-Miss Review owns the
observed defect and the same-class generalized case. The hierarchy owns whether
the child boundary changed in a way that makes parent or sibling assumptions
stale. A patched instance does not make the parent mesh green by itself.

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

## Child Reattachment

Use `ChildReattachmentContract` when a parent mesh depends on a child model that
was just repaired or rerun. It records the parent-side expectation:

- the child model id;
- the child evidence id consumed by the parent;
- expected input and output classes;
- expected state and side-effect ownership;
- expected outgoing guarantees.

If those fields drift, `review_hierarchical_mesh(...)` returns
`child_reattachment_required` instead of green parent confidence.

Child boundary changes propagate upward. If a child changes its risk boundary,
input/output classes, state ownership, side-effect ownership, or outgoing
guarantees, every parent that consumes that child evidence id must review its
target split and reattachment expectations. When a child is also a parent,
continue the same check up the ancestor chain.

If the child evidence comes from a background long-running check, progress logs
are only liveness. Parent confidence requires the final output, error, combined
log, exit, and metadata artifacts before the evidence id can be consumed.

## Mesh Closure Model

Use `MeshClosureModel` when a parent mesh claims the whole parent workflow is
closed, not merely partitioned. The model records:

- `root_entries`: parent entry tokens that start the modeled flow;
- `MeshClosureTransition`: model-to-model handoffs that consume and emit
  abstract output tokens;
- `MeshClosureJoin`: parent join points that require several child or parent
  outputs before emitting the next token;
- `MeshClosureTerminal`: normal exits, failure exits, terminal side-effect
  closures, or out-of-scope dispositions.

`review_mesh_closure_model(...)` blocks when a child output has no consumer, a
required output is unreachable from root entries, a join is incomplete, an
out-of-scope disposition lacks rationale, a terminal is reached while required
outputs remain pending, or a loop-like handoff has no bound or progress rule.

When `HierarchyPartitionMap.closure_model` is present,
`review_hierarchical_mesh(...)` consumes the closure report before returning
`mesh_green_can_continue`. A parent mesh without a closure model may still make
partition, reattachment, or evidence claims, but it should not claim whole-flow
entry-to-exit closure.

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

When one child boundary changes, review only siblings that own, read, depend
on, or share the same parent partition item, state write, side effect,
invariant, failure mode, or outgoing contract. If no sibling is affected, record
the no-overlap reason rather than silently reusing stale sibling assumptions.

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
    ChildReattachmentContract,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
    review_hierarchical_mesh,
    summarize_child_boundary_change,
)

old_payment = ChildModelEvidence("payment", evidence_id="payment:model-check:v0")
new_payment = ChildModelEvidence(
    "payment",
    evidence_id="payment:model-check:v1",
    evidence_tier="abstract_green",
    inputs_accepted=("payment_request",),
    outputs_emitted=("payment_result",),
)
payment_change = summarize_child_boundary_change(old_payment, new_payment)

partition = HierarchyPartitionMap(
    parent_model_id="checkout_root",
    coverage_items=(
        HierarchyCoverageItem("payment", owner_model_id="payment"),
        HierarchyCoverageItem("inventory", owner_model_id="inventory"),
        HierarchyCoverageItem("order_status", ownership="parent"),
    ),
    child_models=(
        new_payment,
        ChildModelEvidence(
            "inventory",
            evidence_tier="abstract_green",
            outputs_emitted=("inventory_result",),
        ),
    ),
    target_split_derivation=ModelTargetSplitDerivation(
        "checkout_root",
        target_child_model_ids=("payment", "inventory"),
        covered_partition_item_ids=("payment", "inventory", "order_status"),
        rationale="derived from checkout model blocks and ownership boundaries",
    ),
    reattachment_contracts=(
        ChildReattachmentContract(
            "payment",
            consumed_evidence_id="payment:model-check:v1",
            expected_inputs=("payment_request",),
            expected_outputs=("payment_result",),
        ),
    ),
    closure_model=MeshClosureModel(
        "checkout_root",
        root_entries=("checkout_start",),
        transitions=(
            MeshClosureTransition(
                "payment_handoff",
                consumes=("checkout_start",),
                emits=("payment_result",),
                consumer_model_id="payment",
            ),
            MeshClosureTransition(
                "inventory_handoff",
                consumes=("checkout_start",),
                emits=("inventory_result",),
                consumer_model_id="inventory",
            ),
        ),
        joins=(
            MeshClosureJoin(
                "checkout_ready",
                required_inputs=("payment_result", "inventory_result"),
                emits=("order_ready",),
            ),
        ),
        terminals=(MeshClosureTerminal("checkout_complete", consumes=("order_ready",)),),
    ),
    boundary_changes=(payment_change,),
)

report = review_hierarchical_mesh(partition)
assert report.ok
```

Run the full example:

```powershell
python examples/hierarchical_model_mesh/run_review.py
```
