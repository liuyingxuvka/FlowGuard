## ADDED Requirements

### Requirement: Reuse consumers verify producer identity and fingerprints
A consumer of prior test evidence SHALL independently compare the immutable
producer receipt and current inputs for execution owner, request, command, test
source, tested artifact, dependencies, environment, result, and coverage scope.
A caller-supplied reusable boolean or status string SHALL NOT satisfy this
comparison.

#### Scenario: Caller asserts current reuse
- **WHEN** a reuse ticket says every input is current but the referenced
  producer receipt or one current fingerprint does not match
- **THEN** reuse SHALL be blocked with the exact mismatched identity

#### Scenario: Immutable receipt matches current inputs
- **WHEN** the producer receipt is terminal success and every required current
  identity and fingerprint matches exactly
- **THEN** the consumer MAY project the reused result without rerunning the
  producer
