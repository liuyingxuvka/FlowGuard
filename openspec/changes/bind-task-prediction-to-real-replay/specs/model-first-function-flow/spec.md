## ADDED Requirements

### Requirement: Production conformance pass requires replay evidence
The model-first runner SHALL require a current conformance replay report or
equivalent structured replay evidence before it reports production
conformance as passing.

#### Scenario: Replay report passes
- **WHEN** a model-first check plan includes a valid current conformance report
  whose replay result is passing
- **THEN** the `conformance_replay` section MAY report pass

#### Scenario: Caller supplies only passing status
- **WHEN** a model-first check plan supplies `conformance_status=pass` without
  a conformance replay report
- **THEN** the `conformance_replay` section MUST report blocked
- **AND** the overall result MUST NOT use that status as production
  conformance evidence

#### Scenario: Caller records non-pass status
- **WHEN** a model-first check plan records failed, blocked, skipped, or
  not-run conformance without a report
- **THEN** the runner MUST keep that non-pass state visible
- **AND** MUST NOT reinterpret it as a pass

### Requirement: Production replay adapters remain independent
FlowGuard conformance guidance and maintained examples SHALL keep expected
model outputs on the comparison side and SHALL NOT supply them to the
production implementation as decision inputs.

#### Scenario: Adapter invokes production code
- **WHEN** an adapter replays an expected model step against production code
- **THEN** it MUST call production code using only real inputs and production
  state
- **AND** compare the independently produced output with the model output
  afterward
