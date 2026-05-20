# Existing Model Preflight Protocol

Existing Model Preflight prevents agents from designing a parallel system before
they understand the FlowGuard models that already describe the current system.

It is a companion route. Pair it with the downstream route that owns the actual
work:

- bug after runtime/test evidence: Model-Miss Review;
- parent/child model or stale child evidence: ModelMesh;
- code refactor or public entrypoint split: StructureMesh;
- implementation structure recommendation: Code Structure Recommendation;
- UI state, control, journey, or implemented UI claim: UI Flow Structure;
- validation hierarchy or slow/stale tests: TestMesh;
- staged development or release confidence: DevelopmentProcessFlow;
- unclear or ordinary behavior/state modeling: model-first kernel.

## Trigger

Use this protocol for non-trivial discussion, analysis, proposal, feature,
bug-fix, refactor, UI, test, prompt, skill, agent-workflow, or process change
inside an existing modeled system.

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
  public entrypoints, and responsibilities when models are found;
- a reuse decision;
- `DuplicateBoundaryRisk` rows for any overlapping ownership;
- downstream FlowGuard routes;
- rationale and stale evidence notes.

## Required Hazards

Known-bad variants should fail or be reported:

- route selected before model search;
- implementation work using only a light note;
- relevant model found but ownership evidence missing;
- new boundary proposed without explaining why existing models cannot carry it;
- duplicate state, side-effect, FunctionBlock, entrypoint, or responsibility
  owner without resolution;
- no model found but search path and reason omitted;
- stale model evidence treated as green.

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
