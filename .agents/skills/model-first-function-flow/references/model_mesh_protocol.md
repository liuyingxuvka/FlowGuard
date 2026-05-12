# Local Model Mesh Protocol

Use this reference when a project already has several FlowGuard models, or when
a model miss suggests that local models are individually deep but disconnected.

## Trigger

Create or update a local model mesh when any of these are true:

- the project has three or more local FlowGuard models;
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

Useful function blocks:

```text
InventoryModels x State -> Set(ModelInventory x State)
IngestChildEvidence x State -> Set(EvidenceTier x State)
ProjectLiveFacts x State -> Set(ProjectedLiveState x State)
CheckCrossModelContracts x State -> Set(ContradictionReport x State)
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

## Prompt Template

Use this prompt shape when asking an agent or officer to build the mesh:

```text
Build or update a FlowGuard model mesh for this project before production work.

Context:
- Project root: <path>
- Planned change or decision: <summary>
- Existing model count: <N>
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
5. Encode the required hazards from `model_mesh_protocol.md` as broken variants.
6. Run Explorer plus progress/stuck review, hazard review, and conformance or
   live projection when applicable.
7. Return a decision: `mesh_green_can_continue`, `add_evidence`,
   `update_child_model`, `split_model_boundary`, `blocked_by_stale_evidence`,
   `blocked_by_cross_model_contradiction`, or `model_coverage_insufficient`.
8. Report what the mesh proves, what it does not prove, and which checks were
   skipped. Skipped is not pass.
```

## Completion Standard

The mesh is sufficient for the current decision only when:

- model inventory is complete enough for the decision boundary;
- each required child model has a freshness rule and evidence tier;
- known-bad hazards fail for the intended reasons;
- skipped or missing live/conformance checks remain visible;
- cross-model contradictions are either absent or converted into blockers;
- the final decision distinguishes model classification from permission to
  continue the real workflow.
