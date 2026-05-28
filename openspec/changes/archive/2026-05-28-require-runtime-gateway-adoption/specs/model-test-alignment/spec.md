# model-test-alignment Delta

## MODIFIED Requirements

### Requirement: Boundary limits are explicit

Code-boundary conformance SHALL remain evidence about a declared boundary's
observed behavior. It SHALL NOT by itself prove that every critical runtime
state write path is mediated by a FlowGuard-backed gateway.

#### Scenario: Trace-level behavior is in scope
- **WHEN** the confidence claim depends on ordered production state, durable
  side effects, external systems, or adapter projection across multiple steps
- **THEN** code-boundary conformance may support the claim but MUST NOT replace
  conformance replay or equivalent production-facing validation

#### Scenario: Boundary report without writer inventory is scoped
- **WHEN** code-boundary conformance is green
- **AND** the project claims FlowGuard protects all critical runtime state
  writes
- **THEN** Model-Test Alignment evidence SHALL be treated as supporting evidence
  only
- **AND** Runtime Gateway Adoption evidence SHALL still be required for the
  runtime protection claim
