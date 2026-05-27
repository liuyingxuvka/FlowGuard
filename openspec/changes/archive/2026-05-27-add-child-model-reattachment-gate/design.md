## Context

ModelMesh already treats a parent model as the total map and child models as
contract-bearing evidence sources. It checks target split derivation, partition
coverage, ownership conflicts, freshness, and evidence tier. That protects the
shape of a parent/child split, but it does not yet let a parent say, in
structured data, "this child repair is still the same handoff I depend on."

Model-miss review already requires the observed failure, a same-class bad case,
rerun model checks, and production-facing validation. For child model repairs,
that is necessary but incomplete: the parent must also consume the updated
child evidence and reject interface drift.

## Goals / Non-Goals

**Goals:**

- Add a compact reattachment contract to ModelMesh parent boundaries.
- Validate child accepted inputs, emitted outputs, owned state, side effects,
  outgoing contract guarantees, and consumed evidence id.
- Make post-runtime model-miss review route child repairs back through the
  affected parent ModelMesh.
- Keep the rule understandable in Skill docs: "child green is not parent green."

**Non-Goals:**

- Do not inline every child state graph into the parent model.
- Do not make Model-Test Alignment, TestMesh, or StructureMesh responsible for
  parent/child model reattachment.
- Do not require every ordinary single-model FlowGuard run to create a mesh.
- Do not add external dependencies or automatic source-code parsing.

## Decisions

1. **Represent parent expectations as a small ModelMesh contract.**
   Add `ChildReattachmentContract` to `flowguard.hierarchy`. It names the child
   model, the input and output classes the parent expects, the state and side
   effect ownership the parent depends on, the outgoing guarantees the parent
   consumes, and the child evidence id the parent accepted.

2. **Extend child evidence rather than creating a separate evidence registry.**
   `ChildModelEvidence` gains optional fields for `evidence_id`,
   `inputs_accepted`, `outputs_emitted`, and `contracts_in`. Existing
   `contracts_out`, state ownership, side-effect ownership, freshness, and tier
   fields remain the main evidence summary.

3. **Check exact handoff only when the parent declares a reattachment contract.**
   Existing meshes stay constructible. When a parent includes reattachment
   contracts, `review_hierarchical_mesh(...)` blocks green confidence on missing
   child evidence consumption, stale evidence id, missing/extra inputs or
   outputs, ownership drift, or missing outgoing guarantees.

4. **Keep model-miss repair and mesh reattachment separate but chained.**
   Model-miss review diagnoses and repairs the missed bug class. ModelMesh
   decides whether the repaired child still fits the parent flow. A child-local
   pass can advance the repair, but it cannot close the miss when parent
   confidence depends on that child.

## Risks / Trade-offs

- [Risk] The new contract feels too heavy for small models. -> Mitigation:
  only require reattachment contracts when a local child repair belongs to a
  parent mesh or the parent claims to consume that child evidence.
- [Risk] Agents treat a stale parent evidence id as harmless because the child
  reran locally. -> Mitigation: add a blocker and required hazard for stale or
  unconsumed child evidence.
- [Risk] Documentation says the rule but tests do not enforce it. ->
  Mitigation: add focused ModelMesh tests and Skill-doc tests for the new gate.
- [Risk] Parent and child terms drift. -> Mitigation: use the same terms across
  code, protocol docs, OpenSpec specs, templates, and changelog.

## Migration Plan

1. Add optional data fields and review findings without breaking existing
   callers.
2. Update focused tests and docs.
3. Run focused tests, then broader regression in the background.
4. Sync installed skills and local workspace copies after validation.
5. Bump patch version and publish a new GitHub release.
