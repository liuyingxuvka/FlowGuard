## ADDED Requirements

### Requirement: Model-Miss Review handles non-trivial bug repairs
The Model-Miss Review route SHALL be used for non-trivial bug repairs when a
real bug, regression, failing test, log, manual validation result, production
evidence, or user-reported failure suggests that an existing model, test, or
confidence claim may have missed a failure class.

#### Scenario: Bug repair enters existing model-miss route
- **WHEN** an agent is asked to repair a non-trivial bug in a modeled or
  model-eligible system
- **AND** the bug is backed by real failure evidence or a user-visible failure
  report
- **THEN** the agent uses the existing Model-Miss Review route rather than
  treating the work as implementation-only

#### Scenario: Tiny bug remains scoped
- **WHEN** a bug repair is a tiny typo, formatting-only issue, or has no
  behavior/state/process confidence impact
- **THEN** the agent may skip Model-Miss Review with a concrete scoped reason

### Requirement: Bug repairs backpropagate the missed condition
Model-Miss Review SHALL ask for false-negative backpropagation evidence for
bug repairs by reusing the existing Plan Intake shape: previous passing claim,
observed failure, supported cause, would-have-failed-if condition, and new
plan/model/repair evidence.

#### Scenario: Root-cause backpropagation is complete
- **WHEN** a bug repair has a previous green claim or confidence statement
- **THEN** the repair evidence names the prior claim, the observed failure, why
  the prior evidence missed it, and which condition would have failed before
  closure if the model or evidence had been strong enough

#### Scenario: Root cause is missing
- **WHEN** a bug repair cannot name a supported cause or a would-have-failed-if
  condition
- **THEN** broad closure remains scoped or blocked until the gap is resolved or
  explicitly out of scope

### Requirement: Bug repair stays in existing route ownership
Model-Miss Review SHALL hand off model-code-test binding, stale evidence,
compatibility classification, legacy path disposition, mesh reattachment, and
final confidence to the existing owning routes instead of defining a separate
bug-fix workflow.

#### Scenario: Handoffs use existing owners
- **WHEN** a bug repair affects code contracts, tests, old paths, child models,
  or final confidence
- **THEN** the Model-Miss Review notes cite Model-Test Alignment,
  DevelopmentProcessFlow, Architecture Reduction, LegacyPathDisposition,
  ModelMesh/TestMesh when relevant, and Risk Evidence Ledger / Closure
  Contract as the owning evidence routes
