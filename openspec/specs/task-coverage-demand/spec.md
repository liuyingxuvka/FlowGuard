# task-coverage-demand Specification

## Purpose
Derive the minimum model and evidence coverage demanded by an exact task so understanding depth is measured against affected reality rather than caller-selected checks.
## Requirements
### Requirement: Task facts determine the coverage denominator
FlowGuard SHALL compile one deterministic coverage demand from the exact task identity, requested outcomes, affected behavior and surfaces, risk facts, lifecycle changes, and current model topology. A caller MAY add demanded coverage but MUST NOT remove a compiler-derived demand.

#### Scenario: Caller omits an affected external surface
- **WHEN** task facts identify a changed external surface that the caller does not list
- **THEN** the compiled demand still contains the surface and its responsible owner

### Requirement: Every demand has an explicit terminal disposition
Every demanded row SHALL identify one owner and finish as exactly one of `satisfied`, `not_triggered`, `unresolved`, or `blocked`; `satisfied` requires current evidence, and `not_triggered` requires a task-grounded reason.

#### Scenario: Required owner did not run
- **WHEN** a demanded owner has neither current evidence nor a valid not-triggered reason
- **THEN** the demand remains unresolved and model maturation cannot close

### Requirement: Cost tiers are derived and monotonic
FlowGuard SHALL derive an ordinary, standard, deep, or release presentation tier from task facts. A higher tier SHALL contain every obligation of lower applicable tiers, and no tier SHALL waive a triggered demand.

#### Scenario: Small task has one high-risk lifecycle change
- **WHEN** an otherwise small task changes a destructive or externally persisted field lifecycle
- **THEN** the compiler includes the lifecycle owner and raises the applicable tier without requiring user selection

### Requirement: Independent task facts define the minimum denominator
The system SHALL compile the minimum task-fact denominator from request, current-model, public-surface, and lifecycle observations rather than accepting a caller-selected list as complete. Each fact SHALL carry its source and SHALL be classified as declared, unknown, omitted, scoped-out, or contradictory. Unknown, omitted, contradictory, or unmapped facts SHALL remain visible and SHALL prevent an unqualified whole-task sufficiency claim.

#### Scenario: Caller supplies a smaller fact list
- **WHEN** an independently observed current-model or public-surface fact is absent from the caller-supplied list
- **THEN** the fact remains in the denominator with its provenance and the whole-task claim is unresolved

#### Scenario: Scope deliberately excludes a fact
- **WHEN** a fact is explicitly excluded by an authorized bounded scope
- **THEN** the fact is preserved as scoped-out and the result can claim only that bounded scope

#### Scenario: One observation plane has no current source snapshot
- **WHEN** request, current-model, public-surface, or lifecycle inspection has no current source reference and fingerprint
- **THEN** the missing plane remains a blocking denominator gap and whole-task sufficiency cannot close

### Requirement: Unresolved facts create explicit coverage demand
The system SHALL assign every unknown, omitted, contradictory, or unmapped task fact to an explicit coverage demand owner or return a blocking unresolved-owner diagnostic.

#### Scenario: No owner exists for an unknown fact
- **WHEN** the compiled denominator contains an unknown fact that no canonical owner accepts
- **THEN** the demand result is blocked and identifies the fact and missing ownership
