## ADDED Requirements

### Requirement: Plan Intake Completeness

FlowGuard SHALL provide a public helper that reviews a structured plan intake
surface before broad model, test, or completion confidence is claimed.

#### Scenario: Complete current intake passes

- **GIVEN** a plan intake with current source evidence
- **AND** every in-scope risk surface is reviewed, included, and mapped to a
  source or evidence id
- **WHEN** the plan-intake helper reviews the plan
- **THEN** the report is OK with full confidence

#### Scenario: Omitted in-scope surface blocks

- **GIVEN** a plan intake with an in-scope risk surface
- **AND** that surface is omitted or has no evidence/source mapping
- **WHEN** the plan-intake helper reviews the plan
- **THEN** the report is blocked and names the omitted surface

#### Scenario: Recurring or high-risk plan needs history

- **GIVEN** a recurring or high-risk plan
- **WHEN** observed failure, same-class generalized case, or historical holdout
  references are missing
- **THEN** the plan-intake helper blocks broad confidence

### Requirement: Evidence Adapter Conformance

FlowGuard SHALL provide a public helper that checks whether project-specific
evidence adapters preserve raw artifact identity, freshness, and status
classification.

#### Scenario: Mapping preserves classification

- **GIVEN** a raw runtime, log, test, code, or history artifact
- **AND** its mapped evidence row preserves the expected classification and
  freshness
- **WHEN** the adapter-conformance helper reviews the mapping
- **THEN** the report is OK

#### Scenario: Known-bad fixture passed blocks

- **GIVEN** a known-bad adapter fixture
- **AND** the adapter did not reject it
- **WHEN** the adapter-conformance helper reviews the mapping
- **THEN** the report is blocked

#### Scenario: Progress-only or stale evidence mapped as passing blocks

- **GIVEN** raw evidence classified as progress-only or stale
- **AND** the mapped evidence row is classified as current passing evidence
- **WHEN** the adapter-conformance helper reviews the mapping
- **THEN** the report is blocked for classification loss

### Requirement: False Negative Backpropagation

FlowGuard SHALL provide a public helper that reviews post-green misses before
the miss can be considered closed.

#### Scenario: Structured backpropagation passes

- **GIVEN** a false-negative case with previous passing claim id, observed
  failure id, cause, and would-have-failed-if condition
- **WHEN** the false-negative helper reviews the case
- **THEN** the report is OK or scoped according to declared gaps

#### Scenario: Missing cause or failing condition blocks

- **GIVEN** a false-negative case without a supported cause or without a
  would-have-failed-if condition
- **WHEN** the false-negative helper reviews the case
- **THEN** the report is blocked

### Requirement: Plan Mutation Review

FlowGuard SHALL provide a public helper that checks declared known-bad plan
mutations against the observed model/check result.

#### Scenario: Known-bad mutation fails as expected

- **GIVEN** a mutation marked expected to fail
- **AND** the observed result is blocked, failed, or not OK
- **WHEN** the mutation helper reviews the results
- **THEN** the report is OK

#### Scenario: Known-bad mutation passes blocks

- **GIVEN** a mutation marked expected to fail
- **AND** the observed result is OK or passing
- **WHEN** the mutation helper reviews the results
- **THEN** the report is blocked

### Requirement: Typed Claim Chain

FlowGuard SHALL provide a public helper that prevents narrow FlowGuard reports
from being promoted into broader confidence claims without required supporting
scope evidence.

#### Scenario: Production confidence requires runtime and risk evidence

- **GIVEN** a target production-confidence claim
- **WHEN** current runtime replay or current risk-evidence support is missing
- **THEN** the claim-chain helper blocks the target claim

#### Scenario: Scoped dependency scopes target confidence

- **GIVEN** a target claim supported by a current scoped dependency
- **WHEN** scoped confidence is allowed
- **THEN** the claim-chain helper is OK with scoped confidence

#### Scenario: Stale dependency blocks

- **GIVEN** a target claim supported by stale evidence
- **WHEN** the claim-chain helper reviews the target claim
- **THEN** the report is blocked
