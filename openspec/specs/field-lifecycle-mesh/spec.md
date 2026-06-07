# field-lifecycle-mesh Specification

## Purpose
This capability defines how FlowGuard accounts for fields by owner, reader, writer, projection, lifecycle, and replacement disposition before adding, folding, or removing field-bearing surfaces.
## Requirements
### Requirement: Complete field lifecycle inventory
FlowGuard SHALL provide a field lifecycle mesh that records every discovered
field at leaf level while allowing parent group summaries by entity, payload,
schema, config, public entrypoint, or prompt/config surface.

#### Scenario: All discovered fields are accounted
- **WHEN** a field lifecycle mesh declares discovered fields for an in-scope
  boundary
- **THEN** every discovered field MUST have a leaf row with field id, location,
  owner group, field role, lifecycle status, behavior impact, reader ids,
  writer ids, and evidence status

#### Scenario: Missing field row blocks full coverage
- **WHEN** a discovered in-scope field has no leaf row
- **THEN** the field lifecycle review MUST report a missing field coverage
  finding and MUST NOT allow full field lifecycle confidence

### Requirement: Behavior-bearing fields project to model obligations
The field lifecycle mesh SHALL project behavior-bearing fields into model,
transition, code, and test obligations consumed by existing FlowGuard routes.

#### Scenario: Behavior field creates projection
- **WHEN** a field affects routing, permission, state, mode, schema version,
  feature flags, replay, migration, side effects, error behavior, or external
  outputs
- **THEN** the field lifecycle review MUST require a projection to a model
  obligation, transition coverage cell, code contract, or explicit scoped-out
  reason

#### Scenario: Non-behavior field stays accounted
- **WHEN** a field is display-only, log-only, metadata-only, or otherwise
  non-behavioral
- **THEN** the field lifecycle mesh MAY keep it out of the high-level behavior
  model only when the leaf row records a scoped-out reason

### Requirement: Field lifecycle captures replacement and disposition
The field lifecycle mesh SHALL represent old, replacement, derived, persisted,
and explicitly preserved fields with current disposition before replacement
work can claim completion.

#### Scenario: Old field disposition is unknown
- **WHEN** a field is marked old, replaced, deprecated, or compatibility-like
- **AND** the field disposition is unknown
- **THEN** full replacement confidence MUST be blocked

#### Scenario: Explicit compatibility is preserved
- **WHEN** a field remains for public compatibility, old data migration, or
  archive authority
- **THEN** the field row MUST record compatibility intent, evidence refs, and
  the owner route that keeps the compatibility surface current

### Requirement: Field lifecycle reports route handoffs
The field lifecycle review SHALL report structured owner-route handoffs for
missing projections, old-field disposition gaps, code-owner gaps, test-evidence
gaps, oversized field groups, and stale field evidence.

#### Scenario: Missing field test routes to Model-Test Alignment
- **WHEN** a behavior-bearing field has a model projection and code owner but
  no current external-contract test evidence
- **THEN** the field lifecycle report MUST include a `model_test_alignment`
  handoff with the missing field obligation id

#### Scenario: Field group is too large
- **WHEN** a field group is too large or layered for one leaf review
- **THEN** the report MUST route the split need to ModelMesh or TestMesh
  instead of treating the field lifecycle mesh as an all-in-one runner

### Requirement: Generated field lifecycle inventory
FlowGuard SHALL provide a generated field inventory that lists dataclass fields with module owner, class owner, field name, inferred lifecycle layer, and behavior-bearing hints before field deletion or folding decisions are made.

#### Scenario: Field-bearing module is audited
- **WHEN** the field inventory generator scans FlowGuard modules
- **THEN** the generated report includes field rows grouped by module and lifecycle layer

#### Scenario: Field cleanup is proposed
- **WHEN** a future maintenance task proposes removing fields
- **THEN** the field inventory is current or the task records why field inventory evidence is scoped out

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

