## ADDED Requirements

### Requirement: Self-maintenance closure reports
Closure Contract SHALL require self-maintenance child reports to include owner guard, artifact kind, closure status, findings, missing inputs, stale evidence, skipped checks, next actions, safe claim, and unsafe claim boundary.

#### Scenario: Child report is partial
- **WHEN** any self-maintenance child report is partial, blocked, downgraded, stale, or skipped
- **THEN** Closure Contract SHALL preserve it as a maintenance obligation rather than converting it into pass evidence
