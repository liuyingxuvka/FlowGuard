## ADDED Requirements

### Requirement: Runnable UI claims include human-operability evidence when user-facing completeness is claimed
UI Implementation Validation SHALL require a current human-operability report
when an agent claims a UI is complete, human-operable, release-ready, or usable
by a person for in-scope user tasks.

#### Scenario: Implementation evidence lacks human-operability report
- **WHEN** an implemented UI has click-through or functional-chain evidence
- **AND** the final claim says users can operate or complete the UI tasks
- **THEN** implementation validation requires a passing or explicitly scoped
  human-operability report for the same target revision
