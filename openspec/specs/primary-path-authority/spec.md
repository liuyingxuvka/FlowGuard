# primary-path-authority Specification

## Purpose
Define one current primary runtime authority per business intent, visible primary failure, no automatic alternate success, and the evidence boundary for broad path-sensitive claims.
## Requirements
### Requirement: Primary path contracts declare one runtime authority
FlowGuard SHALL let callers declare one primary runtime authority for each
business intent before broad implementation, done, release, publish,
production, archive, or full-confidence claims.

#### Scenario: Complete primary path contract passes
- **WHEN** a primary path contract names a business path id, business intent,
  primary entrypoint id, owner model id, owner code contract id, expected
  terminal, failure policy, and current evidence ids
- **THEN** the primary path authority review SHALL treat the primary path as
  declared for that business intent

#### Scenario: Missing primary owner blocks path-sensitive claim
- **WHEN** a path-sensitive claim has no primary entrypoint or owner model
- **THEN** the review SHALL report a missing primary authority finding

### Requirement: Automatic fallback success is rejected
FlowGuard SHALL reject alternate runtime surfaces that are invoked because the
primary path failed and return success for the same business intent.

#### Scenario: Primary failure is masked by alternate success
- **WHEN** a fallback candidate shares the business intent, is invoked on
  primary failure, and returns success
- **THEN** the review SHALL report `primary_failure_masked_by_fallback_success`
- **AND** the report SHALL NOT support broad confidence

#### Scenario: Same-owner retry remains primary path
- **WHEN** a retry is owned by the same primary entrypoint, does not delegate to
  an alternate implementation, and preserves the same authority
- **THEN** the review SHALL NOT classify that retry as alternate runtime
  authority

### Requirement: Non-primary surfaces require disposition
FlowGuard SHALL require every old path, alias, wrapper, helper route,
compatibility facade, old field, backup cache, migration path, and manual
recovery surface in scope to have an explicit non-primary disposition.

#### Scenario: Unknown disposition blocks
- **WHEN** a candidate surface has disposition `unknown`
- **THEN** the review SHALL report `fallback_candidate_unknown_disposition`

#### Scenario: Thin external facade is accepted
- **WHEN** a compatibility facade is explicitly external, delegates to the
  primary path, has no independent state writes or side effects, and has
  current evidence
- **THEN** the review MAY classify it as preserved non-authoritative facade

#### Scenario: Facade with business logic blocks
- **WHEN** a compatibility facade performs business validation, state writes,
  side effects, terminal mutation, or success return independently of the
  primary path
- **THEN** the review SHALL report `facade_contains_business_logic`

### Requirement: Primary failure policy is fail-closed
FlowGuard SHALL preserve primary-path failures as visible blocked or error
states unless the action is a same-owner retry or explicitly manual recovery.

#### Scenario: Visible primary failure is accepted
- **WHEN** the primary path fails and the declared failure policy returns a
  visible error state with repairable feedback
- **THEN** the review SHALL treat the failure as fail-closed

#### Scenario: Manual recovery auto-invoked blocks
- **WHEN** a candidate classified as manual recovery is automatically invoked
  by primary failure, timeout, parse error, missing field, or unknown route
- **THEN** the review SHALL report `manual_recovery_auto_invoked`

### Requirement: Coverage receipts support primary path closure
FlowGuard SHALL expose primary-path authority case ids, shard ids, coverage
receipt ids, and risk gate ids so ContractExhaustionMesh, TestMesh,
Model-Test Alignment, and RiskEvidenceLedger can consume the same boundary.

#### Scenario: Report exposes downstream ids
- **WHEN** a plan declares finite axes and interaction groups
- **THEN** the report SHALL expose generated case ids, shard ids, coverage
  receipt ids, and risk gate ids for downstream routes

#### Scenario: Missing coverage blocks broad claim
- **WHEN** the claim scope is done, release, publish, production, archive, or
  full and no current coverage receipt is present
- **THEN** the review SHALL report `primary_path_cartesian_coverage_missing`

### Requirement: PPA acts as downstream authority for path-sensitive commitments
FlowGuard SHALL let Behavior Commitment Ledger hand path-sensitive commitments
to Primary Path Authority and consume the resulting report, decision, receipt,
and risk gate ids.

#### Scenario: Ledger creates PPA binding
- **WHEN** a behavior commitment is marked path-sensitive
- **THEN** the ledger SHALL require a PPA binding instead of treating alternate-path review as a separate ledger-only concern

#### Scenario: PPA report maps back to commitment
- **WHEN** a PPA report is attached to a behavior commitment
- **THEN** the ledger SHALL preserve the commitment id and expose the PPA decision in the commitment coverage report
