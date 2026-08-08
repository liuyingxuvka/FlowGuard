## ADDED Requirements

### Requirement: ContractExhaustion is the sole same-class defect authority
ContractExhaustion SHALL own the canonical finite observed-problem and same-class case identities used by model-miss closure. Other routes may contribute typed seeds or consume the result, but MUST NOT maintain parallel analogous-defect generators, scan receipts, case identities, or completion gates.

#### Scenario: Model Miss contributes an observed bug
- **WHEN** Model Miss Review identifies an observed problem and its canonical affected relations
- **THEN** ContractExhaustion creates or reuses stable observed and finite same-class case identities with executable oracles
- **AND** ModelMaturation and RiskEvidenceLedger consume those identities rather than a second analogous-scan result

#### Scenario: A parallel same-class generator remains
- **WHEN** another current route generates independent same-class case authority for the same commitment or affected relation
- **THEN** FlowGuard MUST report duplicate authority and block broad closure

### Requirement: Canonical relation handoffs materialize into finite cases and obligations
ContractExhaustionMesh SHALL materialize every in-scope canonical relation endpoint needed by a finite-boundary claim into stable mutation or combination case ids, executable oracles, and typed downstream obligations. The source relation id, endpoint identities, authority fingerprint, and currentness SHALL remain visible, but the relation itself SHALL NOT count as exhausted coverage.

#### Scenario: Canonical relation produces finite cases
- **WHEN** a canonical relation identifies same-intent, shared-owner, affected-sibling, shared-mechanism, adapter-only, duplicate-boundary, or bounded family-member risk
- **THEN** ContractExhaustionMesh generates or references canonical finite cases for every required in-scope endpoint or interaction
- **AND** the report exposes the originating relation ids and materialized owner obligations

#### Scenario: Relation endpoint has no canonical case
- **WHEN** a coverage claim cites a canonical relation but an in-scope endpoint or interaction has no case, oracle, or explicit scoped disposition
- **THEN** ContractExhaustionMesh reports an unmaterialized-relation gap
- **AND** the relation id MUST NOT count as exhausted coverage

#### Scenario: Relation authority changes after generation
- **WHEN** the relation source, endpoints, affected members, behavior plane, or currentness changes after cases or receipts were produced
- **THEN** the dependent cases and receipts become stale
- **AND** current coverage requires rematerialization against the new canonical relation identity

## REMOVED Requirements

### Requirement: Similarity handoffs produce materialized canonical cases and obligations
**Reason**: The materialization protection remains necessary, but the standalone Model Similarity handoff and its separate test/code-obligation identities are retired.
**Migration**: Materialize bounded canonical relation endpoints directly into ContractExhaustionMesh cases, oracles, and native downstream obligations.
