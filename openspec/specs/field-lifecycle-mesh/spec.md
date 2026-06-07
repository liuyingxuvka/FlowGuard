# field-lifecycle-mesh Specification

## Purpose
TBD - created by archiving change enforce-default-replacement-field-lifecycle. Update Purpose after archive.
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

