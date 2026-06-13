## ADDED Requirements

### Requirement: Human-operability task coverage is capability-complete
Human-operability validation SHALL treat the user task coverage ledger as complete only when every required UI functional capability maps to an in-scope user task or an explicitly scoped capability row.

#### Scenario: Capability has user task
- **WHEN** a capability is required and user-visible
- **THEN** the human-operability ledger links that capability through the existing feature/task rows to task frames, primary controls, feedback, cancel/error behavior, keyboard/focus, and walkthrough evidence

#### Scenario: Capability has no task
- **WHEN** a required capability has no user task and no bounded scoped-out row
- **THEN** human-operability confidence is blocked even if visible controls and functional chains pass
