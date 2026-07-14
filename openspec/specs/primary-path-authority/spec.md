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

### Requirement: Each exact business intent has one primary runtime path
Primary Path Authority SHALL key runtime uniqueness by the stable exact
`business_intent_id`. Exactly one `business_path_id` SHALL be primary for that
intent in the declared scope; different path ids SHALL NOT create multiple
primary authorities for the same exact intent.

#### Scenario: Different path ids claim one exact intent
- **WHEN** two primary path contracts have different business path ids but the same stable exact business-intent id
- **THEN** PPA SHALL report a duplicate primary runtime authority blocker and SHALL NOT support broad confidence

#### Scenario: One primary path owns the exact intent
- **WHEN** one complete primary path contract names the stable exact intent, selected path, entrypoint, model owner, code-contract owner, terminal, failure policy, and current evidence
- **THEN** PPA SHALL expose that path as the singular primary authority for the intent

#### Scenario: Material semantic difference is proposed as another intent
- **WHEN** a candidate path claims a separate business-intent id
- **THEN** PPA SHALL require the existing BCL identity and typed external semantic difference instead of accepting a new id based only on a different surface or path name

### Requirement: Primary path selection reuses a current equivalent path
PPA SHALL consume the affected same-intent surface and candidate inventory from
the existing Preflight/BCL handoff. When an equivalent existing path has current
passing RuntimePathEvidence and complete proof-artifact coverage for the same
preconditions, expected terminal, material state writes, and side effects, PPA
SHALL retain that path as the selected primary authority.

#### Scenario: Equivalent current path already exists
- **WHEN** the candidate inventory contains an existing path with matching exact-intent semantics and current passing runtime and proof evidence
- **THEN** PPA SHALL select that existing path and SHALL require additional surfaces to delegate or receive another existing non-primary disposition

#### Scenario: New path attempts to bypass the existing success path
- **WHEN** a proposed new path has the same exact intent and would independently return success while an equivalent current primary path remains valid
- **THEN** PPA SHALL block the new authority and SHALL route the duplicate candidate to the existing Architecture Reduction or replacement process

#### Scenario: Replacement path is necessary
- **WHEN** current evidence proves that the selected path must be replaced
- **THEN** PPA SHALL require an explicit migration or replacement disposition, current parity or transition evidence, and disposal of the old success authority before the replacement supports broad confidence

### Requirement: Primary path confidence requires complete candidate accounting and material evidence
PPA SHALL account for every affected declared UI, API, CLI, alias, adapter,
wrapper, helper, compatibility, migration, cache, old-field, and recovery
surface supplied by the existing same-intent inventory. A green decision SHALL
require current RuntimePathEvidence and proof-artifact coverage for the selected
path; opaque ids or caller-selected candidate subsets SHALL NOT establish
complete primary-path authority.

#### Scenario: Affected candidate surface is omitted
- **WHEN** a known affected same-intent surface has no primary or non-primary disposition in the PPA plan
- **THEN** PPA SHALL report incomplete candidate accounting and SHALL NOT support broad confidence

#### Scenario: Evidence id has no material current proof
- **WHEN** the selected path cites an evidence id but no current passing runtime observation and complete proof artifact bind the exact intent, path, terminal, covered revision, and required obligation
- **THEN** PPA SHALL report a primary-path evidence gap and SHALL NOT return a green decision

#### Scenario: Thin surfaces delegate without another commitment
- **WHEN** an additional UI, API, CLI, alias, adapter, wrapper, or compatibility surface delegates to the selected primary path and owns no independent business result, terminal, state write, or side effect
- **THEN** PPA SHALL preserve it as a non-authoritative surface under the existing commitment and SHALL NOT require or create a delegate commitment

### Requirement: PPA exposes one singular primary path binding
PPA SHALL expose one singular `primary_path_id` for each exact business intent
and SHALL preserve the matching commitment id and business-intent id in the BCL
handoff. Legacy plural input SHALL support only deterministic one-item migration
and SHALL NOT remain the canonical output.

#### Scenario: Singular PPA binding maps back to BCL
- **WHEN** PPA returns a current green decision for a path-sensitive commitment
- **THEN** the handoff SHALL contain the commitment id, exact business-intent id, and one primary path id

#### Scenario: Legacy plural input contains one path
- **WHEN** PPA receives exactly one distinct non-empty legacy primary path value and no conflicting singular value
- **THEN** PPA SHALL normalize it to the singular primary path binding

#### Scenario: Legacy plural input is ambiguous
- **WHEN** PPA receives multiple or conflicting primary path values for one exact business intent
- **THEN** PPA SHALL report ambiguity and SHALL NOT choose a path by list order
