## ADDED Requirements

### Requirement: Canonical-relation-driven family evidence
Model-Test Alignment SHALL consume bounded canonical relation handoffs when a broad finite claim depends on exact sibling, shared-mechanism, same-intent, adapter-only, or evidence-duplicate endpoints. Every required endpoint SHALL bind to a concrete model obligation, owner code contract, and current test evidence, or to an explicit scoped disposition.

#### Scenario: Canonical sibling relation requires member evidence
- **WHEN** an alignment claim cites a current affected-sibling or shared-mechanism relation
- **THEN** the review requires current evidence for each in-scope endpoint obligation or a concrete scoped rationale
- **AND** it preserves the relation id, source authority, endpoint identities, and currentness

#### Scenario: Shared evidence cannot overclaim coverage
- **WHEN** two endpoint obligations cite the same evidence through an evidence-duplicate or shared-mechanism relation
- **THEN** the review accepts that evidence only for obligations whose external contract, mechanism, owner code, provenance, and freshness match its exact scope

#### Scenario: No current relation establishes the family
- **WHEN** a caller claims family-wide alignment from shared wording or shape without a current canonical relation and materialized members
- **THEN** Model-Test Alignment rejects the family-level claim and preserves the missing-relation gap

### Requirement: Canonical relation ids materialize into model-code-test alignment rows
Every in-scope canonical relation consumed by Model-Test Alignment SHALL materialize as concrete model obligations, owner code-contract bindings, test targets, or explicit scoped dispositions. An opaque relation id SHALL NOT satisfy model-code-test coverage.

#### Scenario: Canonical relation is fully materialized
- **WHEN** a canonical relation identifies impacted models or same-intent surfaces requiring code and test coverage
- **THEN** Model-Test Alignment resolves every in-scope endpoint to concrete ModelObligation, owner CodeContract, and current TestEvidence or binding rows
- **AND** the binding report exposes the originating relation and endpoint ids

#### Scenario: Relation id remains opaque
- **WHEN** an alignment plan lists a canonical relation but no concrete alignment row or scoped disposition consumes an in-scope endpoint
- **THEN** Model-Test Alignment reports an unmaterialized relation obligation
- **AND** the opaque id MUST NOT satisfy coverage

#### Scenario: Relation authority changes
- **WHEN** a relation source, endpoint, affected-member set, behavior plane, or currentness changes after alignment evidence was accepted
- **THEN** the dependent alignment rows become stale until rebound to the current relation identity

## MODIFIED Requirements

### Requirement: Plane-aware obligations bind model, owner code, and tests
Required behavior-plane, typed-relation, lookup, preflight, canonical-relation-derived, migration, and Model Miss obligations SHALL each bind one owner public code contract and current tests covering the same contract.

#### Scenario: Lookup obligation has external contract evidence
- **WHEN** plane-first lookup is required for the change claim
- **THEN** Model-Test Alignment SHALL bind the lookup obligation to the public lookup function/CLI contract and current same-plane/wrong-plane tests

#### Scenario: Internal scorer test is insufficient
- **WHEN** evidence tests only an internal token scorer and does not exercise the public lookup report boundary
- **THEN** alignment SHALL report an external-contract coverage gap

#### Scenario: Canonical relation contributes an alignment obligation
- **WHEN** a current canonical relation identifies an affected endpoint whose behavior is in scope
- **THEN** Model-Test Alignment SHALL derive the concrete obligation from that endpoint and bind it to the endpoint's current model owner, public code contract, and current tests
- **AND** the relation SHALL remain provenance rather than an independent obligation owner

#### Scenario: One plane-aware obligation is unbound
- **WHEN** a required obligation lacks a current model, code, or test binding
- **THEN** alignment remains blocked or scoped and the missing layer remains visible

## REMOVED Requirements

### Requirement: Similarity-driven family evidence
**Reason**: The useful sibling and evidence-scope protections remain, but the standalone Model Similarity family and maintenance-group authority is retired.
**Migration**: Use bounded canonical relation endpoints and materialize each required member into native model-code-test rows.

### Requirement: Similarity handoff ids materialize into model-code-test alignment rows
**Reason**: Separate similarity test/code obligation ids duplicate Model-Test Alignment's own obligation and binding owners.
**Migration**: Preserve canonical relation provenance while materializing each endpoint directly into ModelObligation, CodeContract, TestEvidence, or an explicit scoped disposition.
