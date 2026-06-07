# test-result-reuse-proof Specification

## Purpose
This capability defines FlowGuard's Test Result Reuse Proof behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Test result reuse ticket
FlowGuard SHALL provide a public test-result reuse ticket that records why a
previous test result can be reused as current evidence.

#### Scenario: Current reuse ticket supports old result reuse
- **WHEN** a reuse ticket names the current evidence id, previous evidence id,
  reason, command fingerprint, test source fingerprint, tested artifact
  fingerprint, result fingerprint, and current coverage scope
- **AND** command, test source, tested artifacts, dependencies, environment,
  previous result, result fingerprint, and coverage scope are all current
- **THEN** FlowGuard SHALL report no test-reuse ticket gap

#### Scenario: Missing previous result blocks reuse
- **WHEN** a reuse ticket does not name the previous evidence id or previous
  result status is not current
- **THEN** FlowGuard SHALL report a test-reuse gap and SHALL NOT allow the old
  result to count as current evidence

#### Scenario: Changed tested artifact blocks reuse
- **WHEN** a reuse ticket says the tested artifact fingerprint is stale
- **THEN** FlowGuard SHALL report a tested-artifact stale reuse gap

### Requirement: Reused test result requires concrete proof artifact
FlowGuard SHALL require reused test evidence to carry a current proof artifact
for the reused result artifact.

#### Scenario: Proof artifact is current
- **WHEN** reused test evidence has a passing proof artifact with result path,
  matching result fingerprint, current route evidence, and matching covered
  obligation ids
- **THEN** the reused result MAY support current evidence

#### Scenario: Progress-only artifact blocks reuse
- **WHEN** reused test evidence references a progress-only proof artifact
- **THEN** FlowGuard SHALL reject the reused result as completion evidence
