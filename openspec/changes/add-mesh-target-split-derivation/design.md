## Context

The current mesh family already shares a parent/child partition principle.
ModelMesh reviews model partitions, TestMesh reviews validation partitions, and
StructureMesh reviews code structure partitions. For this change, another agent
owns StructureMesh updates; this change is scoped to ModelMesh and TestMesh.

Current ModelMesh and TestMesh APIs consume partition maps and evidence objects.
They do not prove the target child model or child suite layout came from an
internal FlowGuard structure model. That leaves room for agents to invent a
split and then only check ownership after the fact.

## Goals / Non-Goals

**Goals:**

- Require ModelMesh to carry a target model split derivation for parent/child
  model layouts.
- Require TestMesh to carry a target validation split derivation for parent/child
  suite/script layouts.
- Keep the derivation as structured evidence reviewed by the mesh, not a new
  modeling language.
- Preserve routine/release evidence checks and existing parent/child ownership
  semantics.

**Non-Goals:**

- Do not implement automatic source parsing or automatic test discovery.
- Do not expand child model graphs or child test cases into the parent mesh.
- Do not modify StructureMesh behavior in this change.
- Do not require every ordinary FlowGuard model or ordinary test run to create a
  mesh.

## Decisions

1. **Add small derivation dataclasses instead of a new mesh type.**
   ModelMesh gets a `ModelTargetSplitDerivation`; TestMesh gets a
   `TestTargetSplitDerivation`. Each records the source FlowGuard structure
   model, target children, partition coverage, and rationale.

2. **Block missing derivation at the parent boundary.**
   When a ModelMesh partition map or TestMesh plan contains parent/child split
   data, the review requires derivation evidence before returning green
   confidence. This prevents a supplied partition map from becoming authority by
   itself.

3. **Validate enough structure to catch fake derivations.**
   The review checks that derivation evidence names a FlowGuard source model,
   has target child ids, covers partition items, and provides rationale. TestMesh
   additionally checks that target suite ids are registered child suites because
   its target split is the concrete validation layout under review.

4. **Keep split derivation separate from evidence freshness.**
   The derivation explains why the target split exists. Existing evidence tiers,
   stale checks, background completion, and routine/release scopes still decide
   whether the child evidence is trustworthy.

## Risks / Trade-offs

- [Risk] Existing examples and tests omit derivation evidence. -> Mitigation:
  update focused examples/templates/tests and keep defaults backward compatible
  at object construction time while reviews block only when mesh confidence is
  requested.
- [Risk] Agents may write prose rationale without real coverage. -> Mitigation:
  review requires source model id, target children, covered partition ids, and
  rationale; focused tests include fake/missing derivation cases.
- [Risk] ModelMesh and TestMesh drift into different concepts. -> Mitigation:
  use parallel field names, docs wording, and rollout model invariants while
  preserving domain-specific checks.
