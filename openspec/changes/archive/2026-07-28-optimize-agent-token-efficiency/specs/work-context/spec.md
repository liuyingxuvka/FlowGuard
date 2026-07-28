## ADDED Requirements

### Requirement: WorkContext behavior-source admission is explicit
WorkContext artifacts SHALL remain read-only planning and change context by
default. They SHALL enter the expected behavior-source inventory only through
explicit behavior-source-surface identities and an admitted typed mapping.

#### Scenario: Planning artifact has no behavior mapping
- **WHEN** a current proposal, design, task, changelog, Spec Kit, Superpowers,
  or other declared-file artifact has no admitted behavior-source-surface id
- **THEN** it SHALL remain fingerprinted WorkContext and freshness input but
  SHALL NOT create an expected behavior commitment row

#### Scenario: Artifact explicitly maps behavior
- **WHEN** a current WorkContext artifact declares an admitted behavior source
  identity and typed commitment target
- **THEN** coverage inventory MAY include that exact source without treating
  provider status as behavior or validation evidence
