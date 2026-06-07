# runtime-path-evidence Specification

## Purpose
This capability defines FlowGuard's Runtime Path Evidence behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Runtime path evidence rows
FlowGuard SHALL provide structured runtime path evidence rows for expected
workflow nodes, observed real-code nodes, observed run paths, and path alignment
reports.

#### Scenario: Runtime node observation is serializable
- **WHEN** a project records a runtime node observation with model, leaf,
  model path, obligation, code contract, input, output, state write, side
  effect, status, and freshness fields
- **THEN** the observation SHALL expose those fields through a deterministic
  `to_dict()` representation

#### Scenario: Runtime progress identifies its model target
- **WHEN** a project prints or formats runtime progress for an observed node
- **THEN** the output SHALL include the corresponding FlowGuard `model_id`,
  `model_path` when known, `node_id`, run id, and status so an AI or human can
  locate the model being compared without already loading the project context

#### Scenario: Missing node contract fields are rejected
- **WHEN** a runtime node contract is created without a `node_id`
- **THEN** FlowGuard SHALL reject the row instead of accepting anonymous runtime
  path evidence

### Requirement: Runtime path alignment review
FlowGuard SHALL compare expected runtime node contracts with observed runtime
node observations and report missing, extra, stale, non-passing, order, and
behavior-boundary gaps.

#### Scenario: Required node has current observation
- **WHEN** every required runtime node contract has a current passing
  observation bound to the same node id and model obligation
- **THEN** the runtime path alignment report SHALL be OK

#### Scenario: Required node is missing
- **WHEN** a required runtime node contract has no current passing observation
- **THEN** the runtime path alignment report SHALL include a
  `runtime_node_missing_observation` finding

#### Scenario: Observed node emits undeclared behavior
- **WHEN** an observation records an output, state write, side effect, or error
  path outside the node contract
- **THEN** the runtime path alignment report SHALL include an extra-behavior
  finding for that node

#### Scenario: Ordered node appears out of order
- **WHEN** a path contract requires node A before node B
- **AND** the observed run records node B before node A
- **THEN** the runtime path alignment report SHALL include a
  `runtime_path_order_mismatch` finding

### Requirement: Runtime path recorder
FlowGuard SHALL provide a lightweight recorder that project tests and adapters
can use to collect runtime node observations without depending on external
tracing infrastructure.

#### Scenario: Recorder captures a run path
- **WHEN** code records several runtime nodes through the recorder
- **THEN** FlowGuard SHALL return a runtime path run with a stable run id and
  the recorded observations in order

#### Scenario: Recorder output can be used as evidence
- **WHEN** a recorder-produced run is passed to the alignment review
- **THEN** FlowGuard SHALL treat its node observations the same as hand-authored
  observation rows

### Requirement: Runtime path proof artifact support
Runtime path observations and alignment reports SHALL be able to reference
proof artifacts for strict confidence claims.

#### Scenario: Strict evidence has proof artifact
- **WHEN** a runtime path plan requires proof artifacts
- **AND** each required observation has a current passing proof artifact with a
  result path and matching covered obligation
- **THEN** proof-artifact checks SHALL NOT block the path alignment report

#### Scenario: Missing proof artifact blocks strict path evidence
- **WHEN** a runtime path plan requires proof artifacts
- **AND** a required observation lacks a proof artifact
- **THEN** the runtime path alignment report SHALL include a proof-artifact
  finding for that node

