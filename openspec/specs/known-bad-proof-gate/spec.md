# known-bad-proof-gate Specification

## Purpose
Define the proof gate that requires FlowGuard models to include executable
known-bad evidence for the protected failure class, so a correct-looking model
cannot claim confidence until representative bad behavior is caught.
## Requirements
### Requirement: Known-bad proof records are required for formal model claims
FlowGuard SHALL require structured proof that every declared known-bad case for a formal model claim is caught by the model, a scenario, a replay, or a current proof artifact.

#### Scenario: Missing known-bad proof blocks formal confidence
- **WHEN** a formal FlowGuard check plan declares a known-bad case without a matching proof row
- **THEN** FlowGuard MUST block formal model confidence

#### Scenario: Caught known-bad case passes the proof gate
- **WHEN** a known-bad proof row names the declared case, protected error class, evidence method, expected failure, and observed failure
- **THEN** FlowGuard SHALL allow that case to satisfy the known-bad proof gate

#### Scenario: Known-bad case unexpectedly passes
- **WHEN** a known-bad proof row expects failure but records a passing observed result
- **THEN** FlowGuard MUST fail the proof gate

#### Scenario: Stale or skipped known-bad proof blocks
- **WHEN** a known-bad proof row is stale, skipped, not run, running, or progress-only
- **THEN** FlowGuard MUST block formal model confidence

#### Scenario: Protected error mismatch blocks
- **WHEN** a proof row covers a protected error class that is not declared by the minimum model contract or risk intent
- **THEN** FlowGuard MUST block formal model confidence until the mismatch is fixed

### Requirement: Known-bad proof gate reports claim effect
FlowGuard SHALL expose known-bad proof decisions in summary sections and machine-readable report metadata so missing proof cannot be hidden behind a green model run.

#### Scenario: Proof gap appears in summary
- **WHEN** known-bad proof is missing or invalid
- **THEN** the summary report MUST include a named non-pass section with proof-gap findings

#### Scenario: Proof failure affects overall status
- **WHEN** the proof section fails or blocks
- **THEN** the overall formal FlowGuard summary MUST be failed or blocked rather than pass or pass-with-gaps
