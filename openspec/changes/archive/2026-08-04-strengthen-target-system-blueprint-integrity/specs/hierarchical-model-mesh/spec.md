## ADDED Requirements

### Requirement: Blueprint hierarchy proves exact child reattachment
For every child consumed by a parent or sibling, ModelMesh SHALL verify the current child evidence identity, accepted inputs, emitted outputs, state and side effects, guarantees, schema or portable refinement, and exact consumer acknowledgement.

#### Scenario: Parent consumes a stale child identity
- **WHEN** a changed child is locally green but the parent still names an older child fingerprint or receipt
- **THEN** reattachment and parent confidence SHALL be blocked

#### Scenario: Fake input-output labels match by text only
- **WHEN** a child and parent use matching textual labels without compatible typed members, schema, or refinement evidence
- **THEN** the edge SHALL remain unresolved

### Requirement: Whole-flow hierarchy rejects unclosed cycles and joins
A whole-flow hierarchy SHALL account for required joins, every consumed output, normal and failure exits, retry or repeated-input loops, and terminal pending obligations.

#### Scenario: Required child output has no consumer
- **WHEN** a current child emits a required output that no parent, sibling, or typed external owner consumes
- **THEN** whole-flow closure SHALL fail with the exact unconsumed output

### Requirement: Child reattachment consumes current owner-bound evidence
Every validation or runtime evidence id used by a child, relation, or reattachment SHALL exist in the current target evidence registry, carry the current artifact fingerprint, and belong to that exact child/owner evidence binding.

#### Scenario: Child, edge, and reattachment repeat one ghost id
- **WHEN** all three rows repeat the same nonexistent, stale, cross-revision, or other-owner evidence id
- **THEN** topology review SHALL report the exact evidence failure
- **AND** agreement among the three declarations SHALL NOT count as proof
