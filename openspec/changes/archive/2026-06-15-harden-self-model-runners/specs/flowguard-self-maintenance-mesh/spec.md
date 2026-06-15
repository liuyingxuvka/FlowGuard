## ADDED Requirements

### Requirement: Self-maintenance scans runner entry evidence
The self-maintenance mesh SHALL include current self-model runner entry evidence
when it reviews fallback, direct-entry, compatibility, and prompt cleanup risk.

#### Scenario: Runner still uses direct Explorer
- **WHEN** a current `.flowguard` runner script calls `Explorer(...)` directly
- **THEN** self-maintenance evidence MUST classify the runner as a cleanup gap
  instead of treating the model as fully current

#### Scenario: Runner uses formal helper
- **WHEN** a current `.flowguard` runner script delegates through the formal
  workflow-suite helper and adoption audit reports no current direct Explorer
  runner warnings
- **THEN** self-maintenance evidence MAY treat the runner entry path as current
  for this maintenance claim
