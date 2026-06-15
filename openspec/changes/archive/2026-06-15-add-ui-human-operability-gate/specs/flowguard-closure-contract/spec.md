## ADDED Requirements

### Requirement: Final UI claims require human-operability review
FlowGuard ClosureContract SHALL require a current human-operability report
before final statements claim that a UI is human-operable, usable by users,
release-ready, or complete for in-scope user tasks.

#### Scenario: Human-operability report is missing
- **WHEN** a closure contract requires UI human-operability review
- **AND** no current full-confidence or explicitly scoped report exists
- **THEN** closure blocks broad UI release confidence and downgrades the claim
  to technical wiring or model-only confidence
