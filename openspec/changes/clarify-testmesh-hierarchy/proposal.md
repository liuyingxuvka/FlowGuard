## Why

TestMesh already has parent gates, child suites, partition items, owner checks,
freshness checks, and routine/release gates. However, the Skill and public docs
describe it mostly as slow or layered validation evidence management.

That wording can hide the intended symmetry between FlowGuard's three mesh
routes:

- ModelMesh splits large FlowGuard models into parent/child model boundaries.
- TestMesh splits large test scripts, suites, or validation flows into
  parent/child test boundaries.
- StructureMesh splits large scripts, modules, packages, commands, or APIs into
  parent/child structure boundaries.

The missing message is that all three are applications of the same
parent/child partition principle. The object being partitioned changes, but the
core checks remain coverage, ownership, sibling overlap, stale evidence, and
safe parent confidence.

## What Changes

- Reword the Skill Kernel route map so TestMesh triggers on large test
  scripts/suites and hierarchical test decomposition, not only slow evidence.
- Strengthen `test_mesh_protocol.md` and public TestMesh docs with the shared
  mesh principle and nested child-as-parent guidance.
- Update templates so generated TestMesh scaffolds teach parent test gates,
  child test scripts/suites, and evidence contracts together.
- Add focused tests that prevent future wording from narrowing TestMesh back to
  background/slow evidence only.
- Extend the Skill Kernel rollout model with a known-bad case where TestMesh is
  not presented as a sibling hierarchical mesh route.

## Capabilities

### Modified Capabilities

- `test-evidence-mesh`: Clarifies that TestMesh is a test hierarchy mesh for
  splitting large test structures into parent/child validation regions.
- `flowguard-skill-kernel`: Clarifies that ModelMesh, TestMesh, and
  StructureMesh are sibling routes under a shared parent/child partition
  principle.

## Impact

- Skill/docs/templates/tests: wording and focused assertions.
- Runtime package: no new dependency and no schema change expected.
- Release: folds into the unreleased local `v0.9.0` work; GitHub publication
  remains deferred until explicit user approval.
