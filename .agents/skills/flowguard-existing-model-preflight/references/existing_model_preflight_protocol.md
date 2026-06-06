# Existing Model Preflight Protocol

Existing Model Preflight prevents agents from designing a parallel system before
they understand the FlowGuard models that already describe the current system.

It is a companion route. Pair it with the downstream route that owns the actual
work:

- non-trivial bug repair or bug after runtime/test evidence: Model-Miss Review;
- parent/child model or stale child evidence: ModelMesh;
- parent/child/leaf proof chain or finite code boundary matrix: ModelMesh,
  Model-Test Alignment, TestMesh, then layered boundary proof;
- code refactor or public entrypoint split: StructureMesh;
- implementation structure recommendation: Code Structure Recommendation;
- field additions, migrations, replacements, prompt/config fields, schema keys,
  or old-field disposition: FieldLifecycleMesh;
- UI state, control, journey, or implemented UI claim: UI Flow Structure;
- validation hierarchy or slow/stale tests: TestMesh;
- staged development or release confidence: DevelopmentProcessFlow;
- unclear or ordinary behavior/state modeling: model-first kernel.

When the downstream work will make a final confidence claim, preserve model ids,
evidence ids, scoped gaps, and reuse decisions for the Risk Evidence Ledger.
Preflight identifies the existing owner; it does not prove test or runtime
evidence by itself.

## Trigger

Use this protocol for non-trivial discussion, analysis, proposal, feature,
bug-fix, refactor, UI, test, prompt, skill, agent-workflow, or process change
inside an existing modeled system.

For bug-fix work, the preflight should identify the existing model boundary
that owns the failed behavior before Model-Miss Review adds the root-cause,
same-class, model-code-test, or legacy-path closure evidence.

For field-bearing changes, the preflight should also identify existing
FieldLifecycleMesh owners, behavior field ids, and any unresolved field
lifecycle gap before code or model changes begin.

Do not use it for typo-only changes, formatting-only work, direct command
answers, pure read-only explanations, or greenfield work that has no existing
model context.

## Light Mode

Light mode is enough for early thinking. It should say:

- which existing model boundary seems relevant;
- which existing responsibility should be reused or extended;
- where duplicate-boundary risk might appear;
- which downstream route is likely.

Light mode should not claim implementation readiness.

## Full Mode

Full mode is required before implementation, OpenSpec proposal, major
architecture changes, or risky behavior changes.

Use `ExistingModelPreflight` and `review_existing_model_preflight(...)` when
possible. A full report should include:

- `model_search_performed=True`;
- search paths or inventory consulted;
- relevant `ModelContextHit` rows, or `no_model_found` with a reason;
- `ExistingOwnershipSnapshot` for FunctionBlocks, state, side effects,
  public entrypoints, behavior fields, and responsibilities when models are
  found;
- layered proof status for parent models with children: evidence id, parent
  coverage, child disjointness, child reattachment, and leaf boundary-matrix
  status;
- a reuse decision;
- `DuplicateBoundaryRisk` rows for any overlapping ownership;
- downstream FlowGuard routes;
- `field_lifecycle_mesh` as a downstream route when behavior-bearing fields or
  old/replaced fields are in scope;
- rationale and stale evidence notes.

## Required Hazards

Known-bad variants should fail or be reported:

- route selected before model search;
- implementation work using only a light note;
- relevant model found but ownership evidence missing;
- new boundary proposed without explaining why existing models cannot carry it;
- duplicate state, side-effect, FunctionBlock, entrypoint, or responsibility
  owner without resolution;
- behavior-bearing field changed without field lifecycle ownership or a
  downstream FieldLifecycleMesh route;
- no model found but search path and reason omitted;
- stale model evidence treated as green;
- parent model found but parent coverage, child disjointness, child
  reattachment, or leaf boundary-matrix status is unknown when the downstream
  work needs parent/child confidence.

## Output Shape

Recommended short report:

```text
Existing Model Preflight

Task:
- ...

Model search:
- paths:
- hits:

Existing ownership:
- FunctionBlocks:
- State:
- Fields:
- Side effects:
- Public entrypoints:
- Responsibilities:

Reuse decision:
- reuse_existing / extend_existing / add_child_model / new_boundary / no_model_found / skip_with_reason

Duplicate-risk check:
- ...

Recommended downstream route:
- ...
```

## Boundary

This protocol decides whether the agent has understood the current model map.
It does not prove the planned change is correct. Downstream FlowGuard routes and
ordinary tests still provide the behavioral, structural, and release evidence.

If the downstream claim depends on layered proof, preflight should identify the
existing parent model, child models, leaf models, current evidence ids, and any
duplicate-boundary risks before a new model or test boundary is added. A model
reference plus ordinary test mention is not the same as complete finite leaf
boundary proof.
