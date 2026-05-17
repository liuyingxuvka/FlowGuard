## Context

The current implementation is close to the desired model: `TestMeshPlan`
contains a parent suite, partition items, and child suite evidence, while
`review_test_mesh(...)` blocks missing owners, duplicate ownership, stale
evidence, hidden skipped tests, incomplete background runs, and release gaps.

The issue is not primarily an API problem. It is a route-definition and
prompt-governance problem: agents can read "slow/layered validation evidence"
as a performance-only feature, instead of a parent/child decomposition route
for test structures.

## Design

Treat FlowGuard mesh routes as one family:

```text
Large thing         Parent boundary       Child boundary        Mesh route
model               parent model          child model           ModelMesh
test flow/script    parent test gate       child suite/script    TestMesh
code structure      parent module/script   child module/script   StructureMesh
```

TestMesh should keep both sides of its job:

- hierarchy: parent test gate, child test scripts/suites, partition ownership,
  child-as-parent nesting, and sibling overlap checks;
- evidence: command result, freshness, skipped visibility, background
  completion, evidence tier, and routine/release status.

The parent test gate should not inline every child test case, fixture, or state
route. It should consume child contracts:

- what validation region the child owns;
- which state, side effect, command, invariant, or release boundary it covers;
- what input/source freshness rule makes its evidence valid;
- what output evidence proves the child passed or remains pending.

## Non-Goals

- Do not make FlowGuard run project tests directly.
- Do not auto-discover every test file in FlowGuard core.
- Do not merge child suite internals into one giant parent graph.
- Do not rename public APIs in this change.

## Validation

- OpenSpec strict validation for this change.
- Focused docs/template tests.
- Existing TestMesh, Skill docs, public template, and API surface tests.
- FlowGuard rollout model for Skill Kernel modularization, including a
  TestMesh hierarchy narrowing hazard.
