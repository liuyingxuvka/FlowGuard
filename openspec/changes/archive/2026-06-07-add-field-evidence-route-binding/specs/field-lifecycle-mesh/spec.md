## ADDED Requirements

### Requirement: Broad field claims expose evidence route refs
FieldLifecycleMesh SHALL require behavior-bearing field projections to expose
minimal evidence route references when the field lifecycle plan claims full,
runtime, release, production, or closure confidence.

#### Scenario: Broad behavior field has route refs
- **WHEN** a broad field lifecycle plan contains a behavior-bearing field
  projection
- **AND** the projection includes gate, required test, and required replay
  references in `evidence_refs`
- **THEN** FieldLifecycleMesh SHALL allow the field route evidence requirement
  to pass for that projection

#### Scenario: Bounded behavior field remains lightweight
- **WHEN** a bounded field lifecycle plan contains a behavior-bearing field
  projection
- **AND** the projection has no route evidence refs
- **THEN** FieldLifecycleMesh SHALL keep existing bounded behavior and SHALL NOT
  require runtime-style evidence route references

### Requirement: Missing field route refs block broad confidence
FieldLifecycleMesh SHALL report blockers for missing route references that are
required by a broad behavior-bearing field projection.

#### Scenario: Missing gate ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection lacks a gate reference
- **THEN** FieldLifecycleMesh SHALL report a `field_gate_evidence_missing`
  blocker

#### Scenario: Missing negative test ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection requires `failure_path` or `negative_path` evidence
- **AND** the projection lacks a test reference
- **THEN** FieldLifecycleMesh SHALL report a
  `field_negative_test_evidence_missing` blocker

#### Scenario: Missing replay ref blocks broad claim
- **WHEN** a broad field lifecycle plan contains a behavior-bearing projection
- **AND** the projection requires replay evidence or the field has replay
  behavior impact
- **AND** the projection lacks a replay reference
- **THEN** FieldLifecycleMesh SHALL report a
  `field_replay_evidence_missing` blocker

### Requirement: Field route refs remain handoffs
FieldLifecycleMesh SHALL treat evidence route references as handoffs to the
owning proof routes rather than replacing those proof routes.

#### Scenario: Route refs do not replace model-test alignment
- **WHEN** a broad behavior field projection includes route references
- **THEN** FieldLifecycleMesh SHALL still project the field to model
  obligations and code contracts for Model-Test Alignment
- **AND** the route refs alone SHALL NOT prove current passing test evidence

#### Scenario: Route refs do not replace runtime gateway adoption
- **WHEN** a broad behavior field projection includes a gate reference
- **THEN** FieldLifecycleMesh SHALL treat that reference as a runtime or
  boundary handoff
- **AND** runtime-gateway confidence SHALL still require Runtime Gateway
  Adoption evidence when the claim depends on production state mutation
