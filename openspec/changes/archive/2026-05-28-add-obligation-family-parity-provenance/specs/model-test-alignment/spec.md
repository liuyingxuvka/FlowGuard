# model-test-alignment Delta

## ADDED Requirements

### Requirement: Model-Test Alignment consumes family parity gates

Model-Test Alignment SHALL be able to consume declared obligation families and family evidence, then block alignment confidence when family parity or required provenance fails.

#### Scenario: Family parity blocks alignment
- **WHEN** a Model-Test Alignment plan includes an obligation family
- **AND** the family parity report has a missing required member/mechanism cell
- **THEN** the alignment report is not OK
- **AND** it includes a family parity finding.

#### Scenario: Complete family parity supports alignment
- **WHEN** every required family member/mechanism cell has current acceptable evidence
- **THEN** Model-Test Alignment does not add family parity blockers.

#### Scenario: Wrong provenance stays visible
- **WHEN** a test proves post-event behavior but does not prove the required event-generation mechanism
- **THEN** the alignment report keeps the provenance gap visible instead of counting that test as mechanism coverage.
