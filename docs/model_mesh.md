# Local Model Mesh Protocol

Use this reference when a project already has several FlowGuard models, or when
a model miss suggests that local models are individually deep but disconnected.

## Trigger

Create or update a local model mesh when any of these are true:

- the project has three or more local FlowGuard models;
- a single model is too large to review comfortably, such as an estimated or
  observed state count above the configured threshold, defaulting to `10_000`;
- a budgeted model group remains incomplete with pending states;
- a model contains several unrelated functional areas that could be child
  model boundaries;
- a change can affect more than one existing model boundary;
- a green model result is being reused for a changed workflow, changed source,
  changed prompt, changed route, or changed runtime evidence;
- a runtime/test/replay/manual validation failure appears after a FlowGuard
  pass and the old model did not make the bug class visible;
- live state, result files, adoption logs, or conformance evidence disagree.

Do not merge every child model into one giant state graph. The mesh is a
model-of-models: it treats child models as contract-bearing evidence sources
with inputs, outputs, state ownership, freshness, and known
blindspots.

When a child model is repaired after a model miss, a child-local green result is
not parent confidence by itself. The parent mesh must reattach the child through
the input, output, state, side-effect, outgoing-contract, and evidence-id
handoff that the parent flow consumes.

When a broad final claim depends on mesh evidence, report the consumed child
evidence ids and whether each child is still fresh (`python -m flowguard map
check`). ModelMesh owns parent/child reattachment; it does not by itself decide
that a specific user-facing risk is covered.

Keep the current bug instance separate from bug-class responsibility.
Model-Miss Review owns classification of the observed instance and the
same-class family seed. ContractExhaustionMesh owns the generated sibling,
stale-child, unconsumed-child, and no-delta case ids. ModelMesh owns whether the repaired child boundary
still fits the parent and any affected siblings. A patched instance plus a
green child run is not mesh confidence until that class responsibility is
represented or explicitly out of scope and the parent/affected sibling handoffs
have been reviewed.

For hierarchical projects, treat each parent/child boundary as a partition map:
the parent is the total map, child models are region maps, and the mesh checks
whether those regions cover the parent space without unsafe overlap. A child can
become a parent when it grows large enough to split again, so mesh review can
apply at several levels.

Before a parent/child model layout supports mesh confidence, derive the target
child model structure from a FlowGuard source model or model-of-models. The
target split derivation should name the source model, target child model ids,
covered parent partition items, state ownership fields, side-effect ownership
fields, and the rationale for the split. A supplied partition map is review
input, not proof by itself.

## Inventory

Before trusting existing models, write a compact inventory:

| Field | Meaning |
| --- | --- |
| `model_id` | Stable name for the child model. |
| `evidence_id` | Current child evidence id that a parent can consume. |
| `model_file` | Path to the model script. |
| `runner_file` | Path to the check runner, if any. |
| `result_file` | Last persisted result, if any. |
| `risk_boundary` | Bug class or workflow protected by the model. |
| `inputs_accepted` | Abstract input classes this child accepts from the parent or upstream flow. |
| `outputs_emitted` | Abstract output classes this child can return to the parent flow. |
| `state_owned` | Abstract state fields or production fields represented. |
| `contracts_in` | Preconditions or upstream guarantees the child depends on. |
| `contracts_out` | Outputs, guarantees, or evidence other models depend on. |
| `depends_on` | Upstream models, live state, logs, fixtures, or artifacts. |
| `freshness_rule` | What makes this result stale. |
| `blindspots` | Known not-modeled areas and skipped checks. |
| `coverage_owned` | Parent partition items owned by this child. |
| `side_effects_owned` | Side effects this child can emit. |
| `large_model_signal` | Estimated/observed state count, incomplete budgeted run, or unrelated functional areas that trigger split review. |
| `target_split_derivation` | Source FlowGuard model and target child model layout that derived this parent split. |
| `reattachment_contracts` | Parent expectations for repaired child inputs, outputs, ownership, outgoing guarantees, and consumed evidence ids. |
| `closure_model` | FlowGuard-style parent/child handoff model for root entries, child outputs, consumers, joins, terminals, and out-of-scope dispositions. |
| `contract_exhaustion_case_ids` | Canonical case ids projected from closure hazards such as stale child evidence, unconsumed child output, or repeat/no-delta loops. |
| `coverage_receipt_ids` | Ids of `ModelContractCoverageReceipt` rows (model-scoped Cartesian coverage) consumed by this parent or child boundary. |

## Partition And Overlap Review

## Target Split Derivation

For each parent model boundary, record a target split derivation before green
mesh confidence:

- source FlowGuard model or model-of-models id;
- target child model ids;
- parent coverage items represented by the target split;
- state and side-effect owner fields that shaped the split;
- rationale for why these child model regions are the right target structure.

Missing, source-less, target-less, prose-only, or coverage-incomplete target
derivations are blockers. The mesh still should not expand every child state
graph; it derives the target child layout, then consumes each child model as a
contract-bearing evidence source.

When a mesh represents a parent/child hierarchy, add a compact partition map.
The map should classify parent-space items by function, state, input, output,
side effect, invariant, or failure mode. Each item must be one of:

- `child`: exactly one child owns the item;
- `parent`: the parent owns the item;
- `read_only`: a child reads the item but does not own it;
- `shared_kernel`: a deliberate shared kernel owns the item.

Coverage gaps block confidence: every parent-space item needs an owner or an
explicit out-of-scope note. Unsafe overlap also blocks confidence: sibling child
models must not both own the same state write, side effect, or core functional
area. Shared reads are fine; shared ownership needs an explicit shared kernel.

Child boundary changes propagate upward. If a child changes its risk boundary,
accepted inputs, emitted outputs, state ownership, side-effect ownership, or
outgoing guarantees, the parent partition map, target split derivation, and
reattachment contract are stale until reviewed. If the child is also a parent,
the same stale-boundary rule applies to every ancestor that consumes its
evidence id.

Review affected siblings when a child boundary changes. A sibling is affected
when it owns, reads, depends on, or shares the same parent partition item, state
write, side effect, invariant, failure mode, or outgoing contract. Unaffected
siblings do not need ceremony, but the mesh should make the no-overlap reason
visible instead of silently assuming all siblings remain current.

## Child Reattachment Gate

Use this gate whenever a local child model is changed to repair a bug or model
miss and a parent model still needs to trust that child as part of a larger
workflow. The parent should record a compact reattachment contract for the child:

- child model id;
- current child evidence id consumed by the parent;
- input classes the child must still accept;
- output classes the child must still emit;
- state fields and side effects the parent expects the child to own;
- outgoing guarantees or contract ids the parent depends on;
- rationale linking the reattachment to the parent flow.

The parent mesh must block when the child is locally green but the parent did
not consume the updated evidence id, consumed an older child evidence id, or the
child's declared inputs, outputs, state ownership, side-effect ownership, or
outgoing guarantees drift from the parent expectation. This gate does not inline
the child state graph; it checks whether the child can still plug into the
parent's modeled handoff.

When ContractExhaustionMesh emits `ModelContractCoverageReceipt` rows, treat
them as model-local coverage results. A child's coverage is not automatically
parent coverage. List the required child coverage ids in
`HierarchyPartitionMap.required_coverage_receipt_ids` and pass the rows in
`coverage_receipts` before a broad parent or root claim can be green. Missing,
stale, duplicate, incomplete, scoped, blocked, or unconsumed coverage rows keep
the mesh decision scoped or blocked.

## Mesh Closure Model

Use a mesh closure model when a parent mesh claims whole-flow confidence across
the parent/child model network. This is a FlowGuard-style meta-model of the
model connections, not a child-graph expansion. It treats root entries, child
outputs, parent or sibling consumers, joins, normal/failure exits, and explicit
out-of-scope dispositions as finite tokens and obligations.

The closure model should record:

- parent root entry tokens;
- model-to-model closure transitions and the model that consumes each handoff;
- child output tokens that must be consumed;
- required join points and the outputs each join needs;
- normal exits, failure exits, terminal side-effect closures, and
  out-of-scope dispositions with rationale;
- loop-like retry, rejection, or wait handoffs, the repeat-input tokens and
  repeated output tokens,
  repair feedback tokens, and either progress tokens, blocker tokens, or a
  finite iteration bound.

`review_mesh_closure_model(...)` blocks green closure when a root entry is
missing, a consumed token is unknown, a child output has no consumer, a required
output is unreachable from the root entries, a join cannot complete, an
out-of-scope disposition lacks rationale, a terminal is reached with pending
required outputs, or a loop-like handoff lacks repair feedback, a structured
no-delta disposition, or a bound/progress rule.

When `HierarchyPartitionMap.closure_model` is present,
`review_hierarchical_mesh(...)` must consume the closure report before returning
`mesh_green_can_continue`. If a parent partition declares child outputs,
reattachment contracts, or runtime path evidence, the closure model is required
for broad parent green confidence. Without it, the mesh may still support
partition, target-split, evidence, or scoped reattachment facts, but it should
not be described as proving a closed parent/child flow.

Background long-running checks are not pass evidence while they are still
running. Progress output is liveness only. A mesh may consume a long-check
result only after the final output, error, combined log, exit, and metadata
artifacts exist and the freshness rule says they still match this decision.

## Mesh Model Shape

Keep the mesh finite and inspectable. A useful mesh state usually contains:

- registered child models and their declared risk boundaries;
- freshness for each child model;
- model-scoped Cartesian coverage rows and the required child coverage ids;
- live/current run or artifact facts that the decision depends on;
- cross-model dependencies and contract obligations;
- child reattachment contracts and consumed child evidence ids when a repaired
  child supports parent confidence;
- mesh closure root entries, child output obligations, consumers, joins, and
  terminal dispositions when whole-flow parent confidence is claimed;
- skipped, not-run, or parse-error sections;
- current decision: continue, block, add evidence, update child model, or split.
- parent partition coverage, sibling overlap, state ownership, and side-effect
  ownership for hierarchical boundaries;
- large-model split decisions for oversized new or legacy models.

Useful function blocks:

```text
InventoryModels x State -> Set(ModelInventory x State)
IngestChildEvidence x State -> Set(EvidenceTier x State)
ProjectLiveFacts x State -> Set(ProjectedLiveState x State)
CheckCrossModelContracts x State -> Set(ContradictionReport x State)
CheckChildReattachment x State -> Set(ReattachmentReport x State)
CheckPartitionCoverage x State -> Set(CoverageReport x State)
CheckSiblingOverlap x State -> Set(OverlapReport x State)
ReviewMeshClosure x State -> Set(ClosureReport x State)
ReviewLargeModelSplit x State -> Set(SplitDecision x State)
DecideMeshConfidence x State -> Set(ContinueOrBlock x State)
```

## Required Hazards

At minimum, the mesh must make these broken variants fail:

1. Abstract model pass is treated as live permission.
2. Skipped live audit, skipped replay, parse error, or not-run section is hidden
   inside a green result.
3. Stale or foreign result files are reused after source, prompt, route, input,
   or runtime facts changed.
4. A model that is not registered in the inventory is used as trusted evidence.
5. Two child models make incompatible claims about the same state, artifact,
   owner, or handoff.
6. A live blocker, open defect, or unresolved model-miss obligation is hidden
   by a safe-to-continue decision.
7. Conformance is required but missing, skipped, or only claimed by prose.
8. A post-runtime model miss is fixed in code without adding a same-class
   model scenario, invariant, replay adapter, or out-of-scope boundary.
9. The mesh reads sealed/private packet, report, or result bodies instead of
   metadata and explicit evidence ids.
10. Local installed skill/source copies are stale but accepted as current.
11. The mesh expands every child state graph and becomes too large to inspect.
12. The project has three or more FlowGuard models but no mesh decision is
   created before a broad continue/release/completion claim.
13. A single oversized model does not trigger large-model split review.
14. Parent partition items have no child, parent, or shared-kernel owner.
15. Two sibling child models both own the same state write, side effect, or
    core functional area without an explicit shared-kernel boundary.
16. A legacy model is used as strong child evidence before compatibility
    classification and contract wrapping.
17. A repaired child model is green locally, but the parent did not consume its
    updated evidence id.
18. A parent consumes a stale child evidence id after the child model changed.
19. A repaired child changes accepted inputs or emitted outputs without a parent
    reattachment blocker.
20. A repaired child loses state or side-effect ownership that the parent flow
    still depends on.
21. A repaired child drops an outgoing guarantee or contract that the parent
    mesh consumes.
22. The current bug instance passes after a patch, but the bug class is neither
    represented in executable evidence nor explicitly marked out of scope.
23. A child boundary change is accepted without propagating stale-boundary
    review to the parent target split and reattachment contract.
24. An affected sibling model keeps stale ownership, read-only, shared-kernel,
    or outgoing-contract assumptions after a child boundary changes.
25. A background long-running check is accepted as pass evidence from progress
    output, an in-progress log, or a missing exit/result artifact.
26. A parent mesh claims whole-flow closure while a child output has no parent,
    sibling, terminal, or explicit out-of-scope consumer.
27. A parent mesh reaches a terminal disposition while required child outputs or
    join obligations remain pending.
28. A closure model marks a branch out of scope without rationale.
29. A loop-like parent/child handoff is accepted as closed without repair
    feedback, a blocker/progress token, a bound, ranking, or progress rule.
30. A closure model consumes an unknown or foreign output token that is not
    produced by a root entry, child output, transition, or join.
31. A repeated AI packet or rejected input is returned with the same packet or
    token shape and no repair instruction, so the next packet can be identical.
32. A final full-confidence claim cites child model evidence that is stale in
    `python -m flowguard map check` or was never rerun after the change.

## Prompt Template

Use this prompt shape when asking an agent or officer to build the mesh:

```text
Build or update a FlowGuard model mesh for this project before production work.

Context:
- Project root: <path>
- Planned change or decision: <summary>
- Existing model count: <N>
- Large-model signals: <estimated/observed state counts, incomplete budgeted
  groups, or unrelated functional areas>
- Known model files/runners/results: <paths or "scan first">
- Current live/runtime artifacts to project: <paths or "none">
- Protected harms: <what must not slip through>

Tasks:
1. Inventory every local FlowGuard model, runner, result file, adoption log, and
   conformance/replay artifact relevant to this decision.
2. Record whether each model's result is current, skipped or not run.
3. Define freshness rules for each result and mark stale, skipped, not-run, or
   parse-error evidence explicitly.
4. Create or update a model-of-models. Treat child models as evidence contracts;
   do not inline all child internals unless a contradiction requires a narrower
   adapter.
5. For each parent boundary, create a partition map that assigns parent-space
   functions, state, side effects, invariants, and failure modes to a child,
   the parent, read-only use, or an explicit shared kernel.
6. Record the target split derivation from the FlowGuard source model to the
   proposed child model layout. Include source model, targets, coverage, state
   owners, side-effect owners, and rationale.
7. For each repaired child model, record the parent reattachment contract:
   expected inputs, expected outputs, expected state and side-effect ownership,
   expected outgoing guarantees, and the consumed child evidence id.
8. When parent confidence depends on code boundary proof, build layered
   boundary proof from parent coverage, child disjointness, child
   reattachment, and leaf boundary-matrix rows.
9. When whole-flow parent confidence is claimed, or when child outputs,
   reattachment contracts, or runtime path evidence are present, create a mesh
   closure model that records root entries, child outputs, consumers, joins,
   terminals, out-of-scope branches, repeat-input tokens, repair feedback, and
   loop progress or blocker rules.
10. Separate the current bug instance from the bug class: confirm Model-Miss
   Review represented the same-class responsibility or marked it out of scope.
11. When a child boundary changed, propagate that change to the parent
   partition/split/reattachment review and review affected siblings.
12. Treat background progress as liveness only; require final long-check
   artifacts before using the result as evidence.
13. Encode the required hazards from `model_mesh.md` as broken variants.
14. Run the formal check plan plus progress/stuck review, hazard review, and conformance or
   live projection when applicable.
15. Return a decision: `mesh_green_can_continue`, 
   `coverage_gap_blocked`,
   `overlap_too_high_refactor_needed`, `ownership_conflict`,
   `target_split_derivation_required`, `large_model_split_review_required`,
   `child_reattachment_required`, `blocked_by_stale_evidence`,
   `unconsumed_child_output`, `missing_join_point`, `terminal_leak`,
   `loop_progress_required`.
16. Report what the mesh proves, what it does not prove, and which checks were
   skipped. Skipped is not pass.
```

## Completion Standard

The mesh is sufficient for the current decision only when:

- model inventory is complete enough for the decision boundary;
- each required child model has a freshness rule;
- known-bad hazards fail for the intended reasons;
- skipped or missing live/conformance checks remain visible;
- cross-model contradictions are either absent or converted into blockers;
- each parent partition item is covered or explicitly out of scope;
- the target child model layout is derived from a FlowGuard model and covers
  the parent partition items used by the decision;
- repaired child models reattach through current parent-consumed evidence ids
  and stable input, output, state, side-effect, and outgoing-contract handoffs;
- layered proof is green before parent model confidence claims a closed
  real-code boundary: parent coverage is complete, child overlap is legal,
  child evidence is current and reattached, and leaf matrices cover every
  finite `Input x State -> Set(Output x State)` cell or are explicitly blocked;
- whole-flow parent confidence, when claimed, is backed by a green mesh closure
  model that consumes every required child output, completes joins, reaches a
  valid terminal disposition, and keeps out-of-scope, repair-feedback,
  blocker-token, and loop-progress gaps explicit;
- the current bug instance is not confused with bug-class closure; Model-Miss
  Review either represented the same-class responsibility or marked it out of
  scope before mesh confidence is claimed;
- child boundary changes have propagated to every parent that consumes the
  child evidence id;
- boundary-change, reattachment, oversized-model, and duplicate-edge-path
  findings have been resolved or explicitly scoped;
- affected siblings with overlapping ownership, read-only dependency,
  shared-kernel use, or outgoing-contract dependency have been reviewed or
  shown unaffected;
- background long-running checks are used only after final completion artifacts
  and exit status exist;
- sibling overlap is either read-only, shared-kernel-owned, or converted into a
  split/merge/refactor decision;
- oversized new or legacy models have a split-review decision;
- the final decision distinguishes model classification from permission to
  continue the real workflow.

## Where the models live

A project's models are listed in the project map, `.flowguard/map.json`. Run
`python -m flowguard map models` to see them and `python -m flowguard map check`
to see which ones are stale because the code or model files they cover changed
since the map's fingerprints were recorded. A hierarchy is something you
declare in a `HierarchyPartitionMap`: the parent model id, the child models,
and which parent items each child owns. Cross-domain support or influence
belongs in a child's `depends_on`, not in a second structural parent, so each
child keeps exactly one parent in the partition.

When a child model has runtime path evidence, put the current evidence ids on
`ChildModelEvidence.runtime_path_evidence_ids`. The parent reattachment
contract should consume those ids through
`ChildReattachmentContract.consumed_runtime_path_evidence_ids`; otherwise the
parent may know the child model is green but not that it consumed the child's
current real-code path evidence.

For whole-flow parent confidence, the parent boundary also needs a closure
model. The closure model is a small FlowGuard-style model of the model network:
root entries, child-output tokens, parent or sibling consumers, required joins,
normal/failure exits, and explicit out-of-scope dispositions. It proves the
handoffs close without expanding child internals.

When the parent mesh declares child outputs, runtime path evidence, or
reattachment contracts, `review_hierarchical_mesh(...)` requires a closure model
before broad parent green confidence. The mesh can still report local partition
or evidence facts without that model, but it must not say the parent/child route
can continue as a closed flow.

If a child model was changed to repair a bug, its own green result is not enough
for parent confidence. The parent must reattach that child by consuming the
current child evidence id and checking that the child still accepts the expected
inputs, emits the expected outputs, owns the expected state and side effects,
and provides the outgoing guarantees the parent flow depends on.

Keep the bug instance and the bug class separate. Model-Miss Review owns the
observed defect and the same-class family seed. ContractExhaustionMesh owns the
generated same-class, stale-child, unconsumed-child, and no-delta case ids. The
hierarchy owns whether the child boundary changed in a way that makes parent or
sibling assumptions stale. A patched instance does not make the parent mesh
green by itself.

Before the parent mesh trusts a child-model layout, it should record the target
split derivation from a FlowGuard source model or model-of-models. The
derivation names the source model, target child models, covered partition items,
state owner fields, side-effect owner fields, and rationale for the split. A
partition map without this derivation is not enough for green mesh confidence.


## Partition Maps


## Large Model Review

Large model review asks what the next action should be:

- `keep_as_single_model`: the large model is cohesive and evidence is complete;
- `split_into_children`: the model contains separable child areas;
- `merge_with_existing_model`: a candidate child overlaps an existing model;
- `continue_with_budgeted_execution_only`: keep the model for now, but do not
  report incomplete budgeted work as OK.

Automatic split diagnostics provide the trigger before this review is skipped.
When direct model evidence reports state counts above the large-model
threshold, pending budgeted states, separable areas, broad parent obligations,
or background progress-only status, `review_auto_mesh_splits()` routes the
candidate to ModelMesh and keeps broad parent confidence blocked or scoped
until a current target split and child evidence are consumed.


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
rule and skipped checks.


## Minimal API Example

In this example the payment child was rerun (`v0` -> `v1`) without changing
its inputs or outputs, so the parent only needs to reattach the new evidence
id. Changing `inputs_accepted` or `outputs_emitted` between the two versions
would instead return `parent_rerun_required`.

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

old_payment = ChildModelEvidence(
    "payment",
    evidence_id="payment:model-check:v0",
    inputs_accepted=("payment_request",),
    outputs_emitted=("payment_result",),
)
new_payment = ChildModelEvidence(
    "payment",
    evidence_id="payment:model-check:v1",
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
