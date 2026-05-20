---
name: flowguard-existing-model-preflight
description: Use before non-trivial discussion, analysis, proposal, feature work, bug fix, refactor, UI flow change, test change, prompt change, skill change, or agent-workflow change in an existing modeled system so Codex grounds the route in current FlowGuard models before proposing new structure.
---

# FlowGuard Existing Model Preflight

This is a standalone FlowGuard satellite skill and companion preflight. It is a
peer route beside the other FlowGuard skills, but it is not a replacement for
them. Use it to look at the existing FlowGuard model map before choosing or
executing the downstream route.
Return to `model-first-function-flow` when the FlowGuard route is unclear.

Plain rule: first understand the existing model boundaries; then decide whether
to reuse, extend, add a child model, or create a new boundary.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Do not use this skill as a universal top-level route for every task.
- Do not let this skill replace ModelMesh, StructureMesh, UI Flow Structure,
  Model-Miss Review, Model-Test Alignment, TestMesh, DevelopmentProcessFlow, or
  Code Structure Recommendation.
- Prefer existing modeled responsibilities over parallel new ownership. If a
  new model, module, rule, workflow, or ownership boundary is proposed, explain
  why the existing boundary cannot carry it.
- Skipped, stale, missing, or no-model-found evidence must stay visible.

## When To Use

Use it as a companion preflight when an existing modeled system is involved and
the user is discussing, analyzing, proposing, or implementing a non-trivial
change:

- feature addition or behavior change;
- bug fix or model miss;
- architecture or module-structure advice;
- UI flow, UI state, or UI implementation change;
- test strategy, validation, or evidence change;
- prompt, skill, or agent workflow change;
- model hierarchy, parent/child model, or release/process confidence change.

Skip with a reason for trivial typo edits, formatting-only work, direct command
answers, pure read-only explanations, or greenfield work with no existing model
context.

## Light vs Full

Use a light grounding note for discussion and early analysis:

- likely relevant model(s);
- current responsibility boundary;
- reuse-first direction;
- likely downstream FlowGuard route.

Use a full preflight before implementation, OpenSpec proposal, major
architecture decisions, or risky behavior changes:

- model search paths;
- relevant model hits;
- FunctionBlock, state, side-effect, responsibility, and public-entrypoint
  ownership;
- reuse decision;
- duplicate-boundary risks and their resolution;
- downstream FlowGuard route(s);
- stale/no-model-found gaps.

## Workflow

1. Decide whether the task is in an existing modeled system.
2. Search existing FlowGuard models, docs, OpenSpec changes, and relevant
   `.flowguard/` model records.
3. Record the models that may own the requested behavior.
4. Extract existing FunctionBlocks, state owners, side-effect owners,
   public-entrypoint owners, responsibilities, parent/child boundaries, and
   validation evidence.
5. Decide one of: `reuse_existing`, `extend_existing`, `add_child_model`,
   `new_boundary`, `no_model_found`, or `skip_with_reason`.
6. Identify duplicate ownership risks before allowing a new boundary.
7. Use `review_existing_model_preflight(...)` for full preflight reports when
   available.
8. Route to the downstream FlowGuard skill that owns the actual work.

## User-Facing Snapshot

For non-trivial use, show a compact model-grounding snapshot. It can be text or
Mermaid. It should answer:

- what existing model map was consulted;
- which boundary owns the change today;
- whether the change should reuse, extend, or add a boundary;
- which downstream route will handle the work.

The snapshot explains the preflight. It is not validation evidence.

## Owned Helpers

- `ExistingModelPreflight`
- `ModelContextHit`
- `ExistingOwnershipSnapshot`
- `DuplicateBoundaryRisk`
- `review_existing_model_preflight(...)`
- `python -m flowguard existing-model-preflight-template --output .`
- `references/existing_model_preflight_protocol.md`

## Non-Goals

- Do not implement production changes.
- Do not split code; use StructureMesh for existing code refactors.
- Do not derive final module structure; use Code Structure Recommendation.
- Do not govern parent/child model confidence; use ModelMesh.
- Do not repair runtime misses; use Model-Miss Review.
- Do not replace implementation tests, conformance replay, or validation
  evidence.

For detailed route rules, read
`references/existing_model_preflight_protocol.md`.
