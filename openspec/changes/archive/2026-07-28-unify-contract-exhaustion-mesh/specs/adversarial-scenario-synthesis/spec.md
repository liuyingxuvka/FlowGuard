## ADDED Requirements

### Requirement: Challenge scenarios feed contract exhaustion
FlowGuard MUST allow scenario challenge patterns to feed canonical
ContractExhaustionMesh mutation cases when a challenge route is used for
same-class or finite boundary coverage.

#### Scenario: Challenge pattern becomes canonical case
- **WHEN** a repeated, delayed, ABA, stale-state, or terminal-replay scenario is
  required as contract-exhaustion coverage
- **THEN** FlowGuard records or exports a canonical contract mutation case id
  for the challenge route

#### Scenario: Candidate scenario without oracle remains scoped
- **WHEN** a generated challenge scenario has no domain oracle
- **THEN** it remains candidate or scoped evidence and MUST NOT satisfy a
  required contract-exhaustion case
