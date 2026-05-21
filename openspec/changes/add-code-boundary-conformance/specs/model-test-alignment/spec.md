## ADDED Requirements

### Requirement: Code boundary conformance review
The system SHALL provide a Model-Test Alignment helper that compares declared
model-backed code boundaries with real-code observations.

#### Scenario: Accepted inputs stay within the declared output boundary
- **WHEN** a `CodeBoundaryContract` declares allowed input cases, allowed
  outputs, allowed state writes, allowed side effects, and allowed error paths
- **AND** current `CodeBoundaryObservation` rows show real code accepting those
  input cases
- **THEN** the review verifies that every observed output, state write, side
  effect, and error path is declared by the boundary before allowing green
  boundary confidence

#### Scenario: Forbidden input is accepted
- **WHEN** a boundary declares an input case as rejected or forbidden
- **AND** a real-code observation shows that input case was accepted
- **THEN** the review reports a blocker instead of treating the code surface as
  conformant

#### Scenario: Missing input-gate evidence
- **WHEN** a boundary requires input-gate evidence for rejected input cases
- **AND** no current observation proves that a rejected input case is rejected
- **THEN** the review reports missing boundary evidence

#### Scenario: Extra runtime behavior is observed
- **WHEN** an exact boundary observation records an output, state write, side
  effect, or error path not declared by the boundary
- **THEN** the review reports an extra-behavior blocker

### Requirement: Boundary conformance feeds Model-Test Alignment
The system SHALL let `ModelTestAlignmentPlan` include code boundary contracts
and observations so boundary failures block model/test/code alignment claims.

#### Scenario: Alignment blocks on boundary failure
- **WHEN** a Model-Test Alignment plan includes boundary contracts and runtime
  observations
- **AND** the boundary review reports forbidden input acceptance, missing
  boundary evidence, extra output, extra error path, extra state write, extra
  side effect, stale observation, or non-passing observation
- **THEN** `review_model_test_alignment(...)` includes the boundary finding and
  returns a blocked decision

#### Scenario: Legacy plans remain compatible
- **WHEN** a Model-Test Alignment plan does not include boundary contracts or
  observations
- **THEN** existing model-test-only and model-test-code behavior remains
  unchanged

### Requirement: Boundary limits are explicit
The system SHALL document that code-boundary conformance is runtime evidence
for a declared boundary, not exhaustive semantic proof over arbitrary code.

#### Scenario: Trace-level behavior is in scope
- **WHEN** the confidence claim depends on ordered production state, durable
  side effects, external systems, or adapter projection across multiple steps
- **THEN** code-boundary conformance may support the claim but MUST NOT replace
  conformance replay or equivalent production-facing validation
