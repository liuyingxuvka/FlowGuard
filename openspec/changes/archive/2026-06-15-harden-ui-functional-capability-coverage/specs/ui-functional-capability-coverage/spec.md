## ADDED Requirements

### Requirement: UI functional capabilities are inventoried before broad UI claims
FlowGuard SHALL provide a UI functional capability coverage surface that lists required user-visible capabilities before agents claim UI completeness, runnable functionality, release readiness, or user-operable coverage.

#### Scenario: Required capability is inventoried
- **WHEN** a non-trivial UI task claims user-visible functionality is complete
- **THEN** the capability inventory records each required user-visible capability with label, kind, required status, source references when available, dependencies, validation boundaries, and rationale

#### Scenario: Required capability is missing from inventory
- **WHEN** a UI completion claim depends on a function such as load, plot, refresh, export, save, open, generate, render, or delete
- **AND** that function is absent from the capability inventory and not explicitly scoped out
- **THEN** capability coverage blocks broad UI confidence

### Requirement: Capabilities bind to existing UI feature and task evidence
UI functional capability coverage SHALL reuse existing `UIFeatureContract` and `UIUserTaskCoverageLedger` evidence rather than creating a parallel UI route.

#### Scenario: Capability maps to feature and task
- **WHEN** a required capability is in scope
- **THEN** it maps to at least one user-visible feature contract and at least one in-scope user task, or records a scoped-out capability row with reason, owner, validation boundary, and rationale

#### Scenario: Feature omits required capability
- **WHEN** a required capability has no matching feature contract, user task, or scoped-out row
- **THEN** the review reports the capability as missing from the existing UI flow

### Requirement: Capabilities bind to UI journeys, controls, and events
UI functional capability coverage SHALL connect each required capability to the existing UI journey, control, and event model.

#### Scenario: Capability has UI path
- **WHEN** a capability is user-visible and required
- **THEN** it has at least one journey, control, or event binding that exists in the reviewed UI interaction model and journey coverage

#### Scenario: Capability has no UI path
- **WHEN** a required capability has no journey, control, event, pure-UI classification, or scoped blindspot
- **THEN** the review blocks implemented or human-operable UI confidence

### Requirement: Capabilities bind to implementation and output evidence
UI functional capability coverage SHALL require code owner, functional-chain evidence, output contracts, and current evidence for required capabilities when a running UI is claimed implemented or complete.

#### Scenario: Capability has implementation binding
- **WHEN** a required capability is part of a runnable UI claim
- **THEN** the capability has a binding to code owner or code contract, functional chain or implementation run evidence, current revision, result status, evidence reference, and validation boundary

#### Scenario: Result-producing capability has output contract
- **WHEN** a capability produces or changes a chart, table, file, generated artifact, status, preview, data view, or persistent state
- **THEN** it has an output contract that names the required displays/states/data refs, assertion, evidence kind, evidence reference or boundary, and rationale

#### Scenario: Visible container is not output proof
- **WHEN** a chart, table, file area, or status container is visible
- **AND** no output contract proves the expected data/result semantics
- **THEN** capability coverage rejects the evidence as output-incomplete

### Requirement: Capability dependencies are checked
UI functional capability coverage SHALL record prerequisite capability ids and block dependent capability confidence when prerequisites are unproven.

#### Scenario: Plot depends on load
- **WHEN** a plotting capability declares a load-data prerequisite
- **AND** the load-data capability is missing, failed, stale, or scoped out without an accepted boundary
- **THEN** the plotting capability cannot support full implementation confidence

### Requirement: Scoped-out capabilities are bounded
UI functional capability coverage SHALL allow scoped-out capabilities only when the gap is explicitly owned and bounded.

#### Scenario: Capability is deferred with owner
- **WHEN** a required-looking capability is intentionally deferred, manual-only, out of scope, blocked, or replaced
- **THEN** the scoped row records capability id, reason, owner, validation boundary, rationale, and current evidence when available

#### Scenario: Unbounded scope-out fails
- **WHEN** a capability is omitted or scoped out without reason, owner, validation boundary, or rationale
- **THEN** broad UI confidence remains blocked
