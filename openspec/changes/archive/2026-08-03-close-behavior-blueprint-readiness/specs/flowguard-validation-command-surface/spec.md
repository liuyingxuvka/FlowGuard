## ADDED Requirements

### Requirement: Candidate and readiness commands are read-only
FlowGuard SHALL expose composable read-only commands for candidate blueprint discovery and reconstruction-readiness review. These commands SHALL perform no target-source edits, export, reconstruction, missing-owner execution, installation, or authority activation.

#### Scenario: Candidate command finds unresolved semantics
- **WHEN** candidate discovery cannot independently establish one or more behavior contracts
- **THEN** the command SHALL return a nonzero or explicit incomplete terminal with all unresolved ids
- **AND** it SHALL write no project artifact unless explicit export is separately requested

### Requirement: Validation status identifies parent versus child authority
Validation status output SHALL identify whether a current pointer belongs to a child or terminal parent and SHALL reject a child result as evidence for an incomplete parent gate.

#### Scenario: Child current file is passed to parent verifier
- **WHEN** a verifier receives a current pointer whose authority kind is `child`
- **THEN** parent verification SHALL fail with a typed authority-kind mismatch

