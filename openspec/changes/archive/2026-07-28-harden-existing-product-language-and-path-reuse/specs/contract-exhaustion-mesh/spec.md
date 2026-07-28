## ADDED Requirements

### Requirement: ContractExhaustionMesh generates stable behavior-authority identity faults
FlowGuard SHALL generate canonical mutation cases for missing, unknown, stale, and mismatched `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` whenever a finite behavior or path-sensitive boundary includes those identities.

#### Scenario: Stable authority identity is missing
- **WHEN** a required path-sensitive contract omits the stable intent, commitment, or selected primary-path identity
- **THEN** ContractExhaustionMesh SHALL generate a stable missing-authority-identity case
- **AND** its oracle SHALL block downstream broad confidence

#### Scenario: Same intent uses the wrong selected path
- **WHEN** a mutation keeps the expected `business_intent_id` but substitutes another primary-path id
- **THEN** ContractExhaustionMesh SHALL generate a same-intent path-drift case
- **AND** its oracle SHALL reject the alternate path as authority evidence

#### Scenario: Parallel success masks primary failure
- **WHEN** a candidate surface is invoked after selected-primary-path failure and returns business success
- **THEN** ContractExhaustionMesh SHALL generate a parallel-success or fallback-masking case
- **AND** its oracle SHALL require visible primary failure and forbid the alternate success terminal

#### Scenario: Current path proof becomes stale
- **WHEN** the intent, commitment, selected path, owner contract, or candidate inventory changes after runtime or test evidence passed
- **THEN** ContractExhaustionMesh SHALL generate or require a stale-authority-proof case
- **AND** stale evidence SHALL NOT satisfy the refreshed coverage universe

### Requirement: Expected family members and reduction candidates are finite completeness dimensions
FlowGuard SHALL accept expected obligation-family member ids and expected Architecture Reduction candidate ids as declared finite coverage dimensions, and SHALL generate omission cases for required expected items not materialized by their owning route.

#### Scenario: Expected family member is omitted
- **WHEN** an obligation-family coverage dimension contains an expected required member absent from the materialized family and without scoped exclusion
- **THEN** ContractExhaustionMesh SHALL generate a stable omitted-family-member case
- **AND** its oracle SHALL require the family owner to materialize or disposition that member

#### Scenario: Expected reduction candidate is omitted
- **WHEN** a same-intent candidate dimension contains an expected surface absent from Architecture Reduction candidates and without scoped disposition
- **THEN** ContractExhaustionMesh SHALL generate a stable omitted-reduction-candidate case
- **AND** its oracle SHALL block complete candidate-inventory confidence

#### Scenario: Completeness boundary has no expected inventory
- **WHEN** a broad family or reduction completeness claim supplies only materialized rows and declares no independent expected-member or expected-candidate inventory
- **THEN** ContractExhaustionMesh SHALL report a model or coverage-universe gap
- **AND** it SHALL NOT infer completeness from the smaller observed set

### Requirement: Similarity handoffs produce materialized canonical cases and obligations
FlowGuard SHALL require in-scope model-similarity relation, test-obligation, and code-obligation ids to materialize as canonical mutation or combination cases and typed downstream obligations before they support finite-boundary confidence.

#### Scenario: Similarity relation materializes a canonical case
- **WHEN** a similarity relation identifies same-workflow, duplicate-boundary, adapter-only, or same-intent risk
- **THEN** ContractExhaustionMesh SHALL generate or reference canonical cases for the materialized affected members or candidates
- **AND** the report SHALL expose the originating similarity ids and downstream obligation ids

#### Scenario: Similarity id has no canonical case
- **WHEN** a coverage claim cites an in-scope similarity relation, test-obligation, or code-obligation id but no canonical case or explicit scoped disposition consumes it
- **THEN** ContractExhaustionMesh SHALL report an unmaterialized-similarity-id gap
- **AND** the opaque id SHALL NOT count as exhausted coverage

#### Scenario: Similarity inventory changes after case generation
- **WHEN** the impacted model, surface, member, or candidate inventory changes after similarity-derived cases were generated
- **THEN** the corresponding cases and receipts SHALL be stale
- **AND** current coverage SHALL require regenerated materialized cases

### Requirement: ContractExhaustionMesh covers facade delegation and invalid UI exceptions
FlowGuard SHALL generate canonical cases for retained facade delegation and UI consistency exceptions when those boundaries could conceal a second business path or authorize a forbidden behavior difference.

#### Scenario: Facade delegates to the selected primary path
- **WHEN** a facade candidate is classified as retained delegation
- **THEN** ContractExhaustionMesh SHALL require a case proving that the facade reaches the selected primary path and does not own an independent business terminal

#### Scenario: Facade returns independent success
- **WHEN** a retained facade mutation returns business success or performs the primary side effect without delegating to the selected path
- **THEN** ContractExhaustionMesh SHALL generate a rejecting facade-parallel-success case
- **AND** its oracle SHALL forbid retained-facade readiness

#### Scenario: UI exception changes behavior authority
- **WHEN** a UI consistency exception attempts to waive `business_intent_id`, `behavior_commitment_id`, `primary_path_id`, external result, or user intent
- **THEN** ContractExhaustionMesh SHALL generate an invalid-UI-exception case
- **AND** its oracle SHALL reject the exception before UI or alignment confidence

#### Scenario: UI exception changes presentation only
- **WHEN** a current UI exception changes only an allowed presentation field and preserves the stable behavior authority and external result
- **THEN** ContractExhaustionMesh MAY classify the behavior-authority portion as preserved
- **AND** the UI owner SHALL remain responsible for the presentation-specific evidence
