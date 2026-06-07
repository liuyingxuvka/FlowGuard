## Context

FieldLifecycleMesh currently has two useful layers: leaf field rows account the
field inventory, and `FieldProjection` connects behavior-bearing fields to
model obligations, owner code contracts, and required test kinds. Model-Test
Alignment, Runtime Gateway Adoption, runtime path evidence, and Closure
Contract already own the deeper proof work.

The missing piece is lighter: when a field-lifecycle claim is broad enough to
sound like completion or runtime confidence, the field projection should point
to the evidence route that proves the field is gated and exercised. That route
should be human-auditable without duplicating downstream route logic.

## Goals / Non-Goals

**Goals:**

- Add minimal field evidence route checks for broad field-lifecycle claims.
- Reuse `FieldProjection.evidence_refs` and `required_test_kinds`.
- Keep bounded/design-only field lifecycle plans lightweight.
- Keep non-behavior fields scoped out by reason instead of forcing them into
  runtime evidence routes.
- Update public templates and skill guidance so agents build a field route
  view instead of only a dictionary.

**Non-Goals:**

- Do not add a large required `FieldRouteBinding` object.
- Do not require producer/carrier/submitter/runtime-node/proof fields for
  every row.
- Do not make FieldLifecycleMesh run tests, replay adapters, or runtime gateway
  scans.
- Do not replace Model-Test Alignment, Runtime Gateway Adoption, or Closure
  Contract.

## Decisions

1. **Use evidence reference prefixes instead of a new data model.**
   - Decision: classify existing `FieldProjection.evidence_refs` with prefixes
     such as `gate:`, `test:`, and `replay:`.
   - Rationale: the current API already has a route evidence field; adding a
     new object would make simple field work heavier than needed.
   - Alternative rejected: add a large `FieldRouteBinding` dataclass with many
     required columns. It would overfit the audit comment and duplicate sibling
     routes.

2. **Only broad claims require field evidence route references.**
   - Decision: bounded field lifecycle checks stay backward compatible. Full,
     runtime, release, production, or closure claim scopes require route refs
     for behavior-bearing projections.
   - Rationale: design-time field coverage should stay cheap, but broad
     confidence needs an auditable route.
   - Alternative rejected: require route refs for every behavior field in every
     plan. That would be noisy for early modeling and tests.

3. **Derive required refs from existing proof kinds.**
   - Decision: a broad behavior projection always needs a gate ref; if it
     requires failure or negative test kinds, it needs a test ref; if it
     requires replay or has replay behavior impact, it needs a replay ref.
   - Rationale: this keeps the route check tied to declared proof obligations.
   - Alternative rejected: invent new field-specific proof-kind settings.

4. **Let downstream routes keep proof authority.**
   - Decision: FieldLifecycleMesh reports missing route refs and handoffs, while
     Model-Test Alignment and Runtime Gateway Adoption remain responsible for
     proving tests and runtime observations.
   - Rationale: the field layer should be an index into proof, not a second
     proof engine.

## Risks / Trade-offs

- **Risk: Prefix strings are less formal than a typed object.** Mitigation:
  document the accepted prefixes, add focused tests, and leave room for a typed
  object later if repeated misuse appears.
- **Risk: A reference id can point to missing downstream evidence.** Mitigation:
  keep the wording clear that field refs do not replace Model-Test Alignment or
  Runtime Gateway validation.
- **Risk: Broad-claim detection by `claim_scope` can miss custom wording.**
  Mitigation: support common broad terms and keep the template explicit.
