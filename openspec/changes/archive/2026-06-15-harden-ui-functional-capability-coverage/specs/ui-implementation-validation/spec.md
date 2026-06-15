## ADDED Requirements

### Requirement: UI implementation validation consumes capability coverage
UI Implementation Validation SHALL consume current UI functional capability coverage when a running UI is claimed implemented, runnable, complete, or wired for user-visible functions.

#### Scenario: Capability coverage is current
- **WHEN** implementation validation claims complete runnable UI behavior
- **THEN** it references the current capability inventory and a passing capability coverage report for the same model or implementation revision

#### Scenario: Capability coverage is missing
- **WHEN** implementation validation has feature contracts and journey runs
- **AND** no current capability coverage evidence is supplied for an in-scope user-visible function boundary
- **THEN** implementation validation blocks full runnable UI confidence

#### Scenario: Capability output evidence is missing
- **WHEN** a required capability has journey or click evidence
- **AND** its result-producing output contract is missing, failed, stale, or scoped without owner
- **THEN** implementation validation rejects full functional completion for that capability
