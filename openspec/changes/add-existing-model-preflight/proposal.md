## Why

Codex can still propose new modules, workflows, or rules before it has absorbed
the FlowGuard models that already describe an existing system. That leads to
parallel ownership, duplicate behavior, and architecture advice that bypasses
the current model structure.

FlowGuard already has route-specific helpers for code structure, ModelMesh,
StructureMesh, UI flow, model misses, test evidence, and process freshness. The
missing piece is a model-grounding companion step that runs before discussion,
proposal, or implementation in an existing modeled system.

## What Changes

- Add a directly invokable Codex skill, `flowguard-existing-model-preflight`,
  as a peer companion skill.
- Add global routing guidance that grounds non-trivial existing-system
  discussions and changes in existing FlowGuard models before technical route
  selection.
- Add a FlowGuard helper/checker for structured existing-model preflight
  reports, with light and full review modes.
- Add docs, tests, and a template so agents can produce repeatable preflight
  evidence instead of prose-only claims.
- Synchronize source skills, installed skills, local editable install, shadow
  workspace, version, changelog, and repository state.

## Non-Goals

- Do not make the new skill a universal top-level route for every task.
- Do not replace ModelMesh, StructureMesh, UI Flow Structure, Model-Miss
  Review, Model-Test Alignment, TestMesh, DevelopmentProcessFlow, or the
  model-first kernel.
- Do not require heavy reports for casual discussion; light model grounding is
  enough until the task moves toward implementation, proposal, or high-risk
  architecture change.
- Do not automatically rewrite existing models or source files.

## Impact

Agents working in existing modeled systems should first identify relevant
FlowGuard model boundaries, existing FunctionBlocks, state owners, side-effect
owners, public entrypoints, and downstream routes. New boundaries remain
allowed, but only after the report explains why the existing model cannot carry
the change.
