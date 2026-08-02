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
