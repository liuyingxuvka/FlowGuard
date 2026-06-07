## ADDED Requirements

### Requirement: Minimal CI protects release-critical gates
FlowGuard SHALL keep a minimal GitHub Actions workflow for push and pull
request checks that covers install, project adoption, OpenSpec strict
validation, self-maintenance model checks, and focused unit tests.

#### Scenario: CI covers release-critical checks
- **WHEN** code is pushed or proposed through a pull request
- **THEN** CI runs editable install, project audit, OpenSpec strict validation,
  self-maintenance model checks, and focused unit tests before a release claim
  relies on the branch
