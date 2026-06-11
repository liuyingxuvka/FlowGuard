## ADDED Requirements

### Requirement: Artifact payload validation review
Model-Test Alignment SHALL provide artifact payload contract and evidence
helpers that compare declared payload cases with current test, replay, browser,
desktop, or manual evidence. Payload cases SHALL be treated as synthetic inputs
for the real payload surface, and payload evidence SHALL identify concrete
execution proof before it can support alignment confidence.

#### Scenario: Payload contract is satisfied
- **WHEN** an `ArtifactPayloadContract` declares required payload cases and
  expected outputs, errors, state writes, side effects, or round-trip behavior
- **AND** current passing `ArtifactPayloadEvidence` covers every required case
  with external-contract scope
- **AND** each passing payload evidence row includes an evidence reference,
  proof artifact, or equivalent real-surface execution proof
- **THEN** the payload validation report MAY support alignment confidence

#### Scenario: Required payload case is missing
- **WHEN** a required payload case has no current passing evidence
- **THEN** the payload validation report MUST include a missing-payload-evidence
  blocker

#### Scenario: Payload evidence lacks real execution proof
- **WHEN** a current passing external payload evidence row only declares
  observed fields and does not identify evidence reference, proof artifact, or
  equivalent execution proof for the real payload surface
- **THEN** the payload validation report MUST include an execution-proof blocker
- **AND** that row MUST NOT support green payload confidence

#### Scenario: Payload evidence is stale or non-passing
- **WHEN** payload evidence is stale, skipped, failed, timeout, not-run,
  running, progress-only, or error
- **THEN** it MUST NOT count toward payload coverage

#### Scenario: Payload output mismatches contract
- **WHEN** payload evidence observes an output, error path, state write, side
  effect, or round-trip result outside the declared contract
- **THEN** the payload validation report MUST include a mismatch blocker
