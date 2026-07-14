## ADDED Requirements

### Requirement: Behavior-plane replacement fields are fully accounted
FieldLifecycleMesh SHALL account the new BCL plane, actor-kind, relation, lookup-binding, canonical-ledger, preflight lookup, similarity plane, and Model Miss identity fields with owners, readers, writers, projections, lifecycle, and evidence handoffs.

#### Scenario: BCL schema fields have one owner
- **WHEN** the behavior commitment schema is replaced by the current shape
- **THEN** each added field SHALL have one field owner and identified readers/writers
- **AND** behavior-bearing fields SHALL project to Model-Test Alignment and ContractExhaustionMesh

#### Scenario: Prompt fields are updated
- **WHEN** affected skill prompts or contract sources add plane-selection instructions
- **THEN** the prompt/config field inventory SHALL record canonical source, generated projection, installed projection, and freshness owner

### Requirement: Former dependency field has a closing disposition
`dependency_commitment_ids` SHALL be classified as deleted and rejected; no current reader or translator may remain.

#### Scenario: Runtime object still accepts former dependency
- **WHEN** current runtime construction accepts `dependency_commitment_ids` as a successful relationship authority
- **THEN** FieldLifecycleMesh SHALL report an open replacement-disposition blocker

#### Scenario: Former field reaches a current boundary
- **WHEN** any current loader receives the old field
- **THEN** it SHALL reject the record and require direct typed-relation authorship

### Requirement: Former diagnostic fields cannot masquerade as production state
Former fields such as `unclassified` plane status and manual-conversion reason SHALL NOT become accepted production commitment values or current report fields.

#### Scenario: Unclassified row reaches runtime ledger
- **WHEN** a canonical runtime ledger contains an unclassified value
- **THEN** field lifecycle and ledger review SHALL block broad confidence
