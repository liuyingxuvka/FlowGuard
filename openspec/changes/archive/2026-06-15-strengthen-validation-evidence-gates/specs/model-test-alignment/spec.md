## ADDED Requirements

### Requirement: Artifact payload validation review
Model-Test Alignment SHALL provide artifact payload contract and evidence
helpers that compare declared payload cases with current test, replay, browser,
desktop, or manual evidence.

#### Scenario: Payload contract is satisfied
- **WHEN** an `ArtifactPayloadContract` declares required payload cases and
  expected outputs, errors, state writes, side effects, or round-trip behavior
- **AND** current passing `ArtifactPayloadEvidence` covers every required case
  with external-contract scope
- **THEN** the payload validation report MAY support alignment confidence

#### Scenario: Required payload case is missing
- **WHEN** a required payload case has no current passing evidence
- **THEN** the payload validation report MUST include a missing-payload-evidence
  blocker

#### Scenario: Payload evidence is stale or non-passing
- **WHEN** payload evidence is stale, skipped, failed, timeout, not-run,
  running, progress-only, or error
- **THEN** it MUST NOT count toward payload coverage

#### Scenario: Payload output mismatches contract
- **WHEN** payload evidence observes an output, error path, state write, side
  effect, or round-trip result outside the declared contract
- **THEN** the payload validation report MUST include a mismatch blocker

### Requirement: Payload validation feeds Model-Test Alignment
Model-Test Alignment SHALL let plans include artifact payload contracts and
evidence so payload failures block model/test/code alignment claims.

#### Scenario: Alignment blocks on payload failure
- **WHEN** a Model-Test Alignment plan includes payload contracts or evidence
- **AND** payload validation reports missing, stale, non-passing, scoped, or
  mismatched evidence
- **THEN** `review_model_test_alignment(...)` MUST include equivalent findings
  and return a blocked or scoped decision

#### Scenario: Legacy plans remain compatible
- **WHEN** a Model-Test Alignment plan has no artifact payload contracts or
  evidence
- **THEN** existing model-test, code-contract, boundary, field, and runtime-path
  behavior remains unchanged
