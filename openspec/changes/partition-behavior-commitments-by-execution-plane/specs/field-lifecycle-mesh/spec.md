## ADDED Requirements

### Requirement: Behavior-plane upgrade fields are fully accounted
FieldLifecycleMesh SHALL account the new BCL plane, actor-kind, relation, lookup-binding, canonical-ledger, preflight lookup, similarity plane, and Model Miss identity fields with owners, readers, writers, projections, lifecycle, and evidence handoffs.

#### Scenario: BCL schema fields have one owner
- **WHEN** the behavior commitment schema is upgraded
- **THEN** each added field SHALL have one field owner and identified readers/writers
- **AND** behavior-bearing fields SHALL project to Model-Test Alignment and ContractExhaustionMesh

#### Scenario: Prompt fields are updated
- **WHEN** affected skill prompts or contract sources add plane-selection instructions
- **THEN** the prompt/config field inventory SHALL record canonical source, generated projection, installed projection, and freshness owner

### Requirement: Legacy dependency field has a closing disposition
`dependency_commitment_ids` SHALL be classified as a replaced runtime field with boundary-only migration and no continuing runtime fallback.

#### Scenario: Runtime object still accepts legacy dependency
- **WHEN** normal post-upgrade runtime construction accepts `dependency_commitment_ids` as a successful relationship authority
- **THEN** FieldLifecycleMesh SHALL report an open replacement-disposition blocker

#### Scenario: Upgrader reads legacy field
- **WHEN** the artifact upgrader reads the old field to create typed relations
- **THEN** the field MAY remain visible only as migration input with owner, evidence, and closing disposition

### Requirement: Migration diagnostic fields cannot masquerade as production state
Migration-only fields such as `unclassified` plane status and manual-conversion reason SHALL remain upgrade-report fields and SHALL NOT become accepted production commitment values.

#### Scenario: Unclassified row reaches runtime ledger
- **WHEN** a canonical runtime ledger contains a migration-only unclassified value
- **THEN** field lifecycle and ledger review SHALL block broad confidence
