# model-miss-review Specification

## Purpose
Define how concrete post-green failures backfeed the existing plane-local commitment and owner, generalize the missed class, and close it with current model-code-test evidence.
## Requirements
### Requirement: Model miss review backfeeds behavior registration without creating duplicate features
FlowGuard SHALL use model-miss evidence to check whether the failed external
behavior was already registered before changing the Behavior Commitment Ledger.

#### Scenario: Existing commitment owns the missed behavior
- **WHEN** runtime, test, replay, log, or manual validation evidence fails after a green FlowGuard claim
- **AND** an existing commitment covers the observed external behavior
- **THEN** Model Miss Review SHALL repair the owner model, code contract, tests, same-class/DCAR coverage, and evidence under the existing commitment
- **AND** it SHALL NOT require a new behavior commitment for the point failure

#### Scenario: Miss exposes unregistered external behavior
- **WHEN** model-miss evidence exposes external behavior that no commitment covers
- **THEN** Model Miss Review SHALL route to Behavior Commitment Ledger coverage-gap backfill

### Requirement: Model miss identifies whose promise failed
Every in-scope Model Miss repair SHALL identify an affected behavior plane, affected commitment id when one exists, and primary owner model before creating or changing a commitment.

#### Scenario: AI forgot an operational step
- **WHEN** runtime evidence shows the acting AI omitted a registered port-bridge or health-check step while the product contract itself remained correct
- **THEN** the miss SHALL be classified against `agent_operation`
- **AND** SHALL NOT create a product-runtime commitment for the omission

#### Scenario: Product proxy is wrong
- **WHEN** runtime evidence shows the product proxy or service contract itself is wrong
- **THEN** the miss SHALL be classified against `product_runtime` even if an AI observed the failure

### Requirement: Miss backfeed searches the same plane first
Model Miss review SHALL search the selected plane for an existing commitment and owner model before selecting `coverage_gap_backfill`.

#### Scenario: Existing commitment is extended
- **WHEN** an existing same-plane commitment covers the failed promise
- **THEN** repair SHALL retain the commitment id, update the owner model/cases/evidence as needed, and MAY add a stable error signature
- **AND** SHALL NOT create a duplicate commitment

#### Scenario: Promise was never registered
- **WHEN** no same-plane commitment covers the observed external promise
- **THEN** repair SHALL create or request one gap-backfill commitment in that plane with one primary owner

### Requirement: Multi-plane incidents retain one primary miss
An incident involving more than one behavior plane SHALL record one primary failed promise and typed related commitments rather than one mixed commitment.

#### Scenario: Development validation failed to catch an agent omission
- **WHEN** the primary failure is an agent-operation omission and the development process also lacked a validating gate
- **THEN** the miss SHALL keep the agent commitment primary and link the development commitment as governing or validating context

### Requirement: Miss error signatures feed lookup without becoming proof
Stable observed error signatures MAY be added to the owning commitment lookup binding, but SHALL NOT replace current repair tests, owner code contracts, or same-class evidence.

#### Scenario: Error signature is registered
- **WHEN** a Model Miss closes with current observed and same-class evidence
- **THEN** the signature MAY improve future lookup
- **AND** the lookup binding alone SHALL NOT support closure confidence
