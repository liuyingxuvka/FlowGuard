## ADDED Requirements

### Requirement: Observed authority binds behavior-level blueprint evidence
The sole observed model-system authority SHALL reference the exact owner-level, behavior-block, resource, intent, test-binding, and reconstruction-readiness identities used for a self-qualification claim. A later layer SHALL NOT hide an earlier incomplete or stale layer.

#### Scenario: Current model snapshot points to an owner-level-only blueprint
- **WHEN** the observed snapshot is current but its behavior-block or readiness evidence is incomplete
- **THEN** observed model authority SHALL remain current for its declared model boundary
- **AND** the stronger software-DNA readiness claim SHALL remain incomplete

