## ADDED Requirements

### Requirement: TestMesh owns large payload evidence matrices
TestMesh SHALL allow large artifact payload validation matrices to be split
into child suites or scripts with explicit case ownership and current evidence.

#### Scenario: Child suite owns payload cases
- **WHEN** a parent validation gate declares required payload case ids
- **THEN** each required case id MUST be owned by a registered child suite or
  script with current passing evidence before parent confidence is green

#### Scenario: Payload matrix is too large for a flat claim
- **WHEN** payload validation includes many cases, slow cases, release-only
  cases, browser/manual-heavy cases, or background jobs
- **THEN** TestMesh MUST preserve child evidence status instead of allowing a
  flat green parent summary to hide stale, skipped, not-run, or scoped cases

### Requirement: TestMesh does not decide payload semantics
TestMesh SHALL preserve payload case ids and evidence freshness while leaving
payload semantics to Model-Test Alignment.

#### Scenario: Parent mesh is current but semantics are unbound
- **WHEN** child suites have current evidence for required payload case ids
- **THEN** TestMesh can support evidence freshness
- **AND** Model-Test Alignment remains responsible for deciding whether the
  evidence satisfies the artifact payload contract
