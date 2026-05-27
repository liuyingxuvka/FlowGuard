## Why

FlowGuard now allows user-facing Mermaid diagrams, but the guidance is still too
lightweight and mostly appears near final evidence reporting. In practice,
agents often complete non-trivial modeling work without showing the user the
model shape, route, branch coverage, evidence status, or claim boundary while
the work is happening.

Users need to see enough of the model during the work to understand what
FlowGuard is doing and why the modeling step matters. The goal is not to force
diagrams into tiny tasks; it is to make non-trivial FlowGuard work visible by
default.

## What Changes

- Strengthen FlowGuard prompt guidance so non-trivial FlowGuard work defaults to
  a user-facing Mermaid model snapshot during the work.
- Keep an explicit escape hatch for tiny, obvious, mechanical, or user-suppressed
  tasks.
- Require diagrams to explain the model, route, branch coverage, evidence,
  missing paths, and claim boundaries without counting as validation evidence.
- Add route-specific visibility guidance for all directly installed FlowGuard
  satellite skills, not only UI Flow Structure, ModelMesh, and
  DevelopmentProcessFlow.
- Align global AGENTS guidance, repository AGENTS snippet, README, tests, and
  installed skill copies.

## Capabilities

### New Capabilities

- `flowguard-model-visibility`: Stronger user-facing model visibility guidance
  for non-trivial FlowGuard work.

### Modified Capabilities

- `flowguard-global-routing`: Adds model-visibility guidance to the direct
  FlowGuard route table.
- `model-first-function-flow`: Moves diagram guidance from final evidence only
  into the working model snapshot flow.
