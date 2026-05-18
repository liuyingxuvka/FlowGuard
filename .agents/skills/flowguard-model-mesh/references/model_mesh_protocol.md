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
with inputs, outputs, state ownership, evidence tier, freshness, and known
blindspots.

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
input, not authority by itself.

## Inventory

Before trusting existing models, write a compact inventory:

| Field | Meaning |
| --- | --- |
| `model_id` | Stable name for the child model. |
| `model_file` | Path to the model script. |
| `runner_file` | Path to the check runner, if any. |
| `result_file` | Last persisted result, if any. |
| `risk_boundary` | Bug class or workflow protected by the model. |
| `state_owned` | Abstract state fields or production fields represented. |
| `contracts_out` | Outputs, guarantees, or evidence other models depend on. |
| `depends_on` | Upstream models, live state, logs, fixtures, or artifacts. |
| `evidence_tier` | Current tier from the list below. |
| `freshness_rule` | What makes this result stale. |
| `blindspots` | Known not-modeled areas and skipped checks. |
| `coverage_owned` | Parent partition items owned by this child. |
| `side_effects_owned` | Side effects this child can emit. |
| `large_model_signal` | Estimated/observed state count, incomplete budgeted run, or unrelated functional areas that trigger split review. |
| `target_split_derivation` | Source FlowGuard model and target child model layout that derived this parent split. |

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

Suggested evidence tiers:

- `candidate_only`: model exists but has not produced trustworthy current
  evidence.
- `abstract_green`: abstract Explorer/invariant checks passed.
- `hazard_green`: known-bad hazard variants fail for the intended reasons.
- `live_current_green`: current runtime state or current artifact projection was
  checked against the model boundary.
- `conformance_green`: production or artifact replay conforms to model traces
  or projected states.
- `mesh_green`: the model mesh confirms no cross-model contradiction, stale
  dependency, missing hazard, or hidden skipped check blocks the decision.

Never use `abstract_green` alone as permission to continue a live workflow when
live evidence or conformance is required.

## Mesh Model Shape

Keep the mesh finite and inspectable. A useful mesh state usually contains:

- registered child models and their declared risk boundaries;
- evidence tier and freshness for each child model;
- live/current run or artifact facts that the decision depends on;
- cross-model dependencies and contract obligations;
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
CheckPartitionCoverage x State -> Set(CoverageReport x State)
CheckSiblingOverlap x State -> Set(OverlapReport x State)
ReviewLargeModelSplit x State -> Set(SplitDecision x State)
DecideMeshAuthority x State -> Set(ContinueOrBlock x State)
```

## Required Hazards

At minimum, the mesh must make these broken variants fail:

1. Abstract model pass is treated as live permission.
2. Skipped live audit, skipped replay, parse error, or not-run section is hidden
   inside a green result.
3. Stale or foreign result files are reused after source, prompt, route, input,
   or runtime facts changed.
4. A model that is not registered in the inventory is used as authority.
5. Two child models make incompatible claims about the same state, artifact,
   owner, or handoff.
6. A live blocker, open defect, or unresolved model-miss obligation is hidden
   by a safe-to-continue decision.
7. Conformance is required but missing, skipped, or only claimed by prose.
8. A post-runtime model miss is fixed in code without adding a same-class
   model scenario, invariant, replay adapter, or out-of-scope boundary.
9. The mesh reads sealed/private packet, report, or result bodies instead of
   metadata and explicit evidence pointers.
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
2. Classify each model's evidence tier:
   candidate_only, abstract_green, hazard_green, live_current_green,
   conformance_green, or mesh_green.
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
7. Encode the required hazards from `model_mesh_protocol.md` as broken variants.
8. Run Explorer plus progress/stuck review, hazard review, and conformance or
   live projection when applicable.
9. Return a decision: `mesh_green_can_continue`, `add_evidence`,
   `update_child_model`, `split_model_boundary`, `coverage_gap_blocked`,
   `overlap_too_high_refactor_needed`, `ownership_conflict`,
   `target_split_derivation_required`, `large_model_split_review_required`,
   `blocked_by_stale_evidence`, `blocked_by_cross_model_contradiction`, or
   `model_coverage_insufficient`.
10. Report what the mesh proves, what it does not prove, and which checks were
   skipped. Skipped is not pass.
```

## Completion Standard

The mesh is sufficient for the current decision only when:

- model inventory is complete enough for the decision boundary;
- each required child model has a freshness rule and evidence tier;
- known-bad hazards fail for the intended reasons;
- skipped or missing live/conformance checks remain visible;
- cross-model contradictions are either absent or converted into blockers;
- each parent partition item is covered or explicitly out of scope;
- the target child model layout is derived from a FlowGuard model and covers
  the parent partition items used by the decision;
- sibling overlap is either read-only, shared-kernel-owned, or converted into a
  split/merge/refactor decision;
- oversized new or legacy models have a split-review decision;
- the final decision distinguishes model classification from permission to
  continue the real workflow.
