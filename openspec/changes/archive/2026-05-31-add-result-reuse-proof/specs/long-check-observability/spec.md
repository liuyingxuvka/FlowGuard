## ADDED Requirements

### Requirement: Long checks distinguish proof reuse from progress reuse
Long-running FlowGuard checks SHALL distinguish completed result reuse from
progress output reuse for model and test regressions.

#### Scenario: Completed result can be reused
- **WHEN** a model or test regression result already has final exit/status and
  result artifacts
- **AND** the appropriate reuse ticket proves the current scope still matches
- **THEN** the long-check report MAY mark the result as validly reused

#### Scenario: Progress output cannot be reused as pass evidence
- **WHEN** a background check has only progress output or missing final result
  artifacts
- **THEN** the long-check report SHALL treat it as liveness evidence only, not
  completion evidence
