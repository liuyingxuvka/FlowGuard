## MODIFIED Requirements

### Requirement: Runtime path alignment review
FlowGuard SHALL compare expected runtime node contracts with observed runtime
node observations and report missing, extra, stale, non-passing, order, and
behavior-boundary gaps. When exact path review is required, the comparison
SHALL preserve every ordered occurrence and compare each occurrence's
terminal, state writes, and side effects with its corresponding observation.

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

#### Scenario: Repeated node occurrence is missing
- **WHEN** the exact path contract declares node A twice at distinct sequence
  indices
- **AND** the observed run contains node A only once
- **THEN** the runtime path alignment report MUST report an exact path
  sequence mismatch

#### Scenario: Exact path has an extra occurrence
- **WHEN** the exact path contract declares one occurrence of node A
- **AND** the observed run contains two occurrences of node A
- **THEN** the runtime path alignment report MUST report an exact path
  sequence mismatch unless uncontracted nodes are explicitly allowed

#### Scenario: Occurrence behavior differs
- **WHEN** an expected exact-path occurrence declares a terminal, state-write
  sequence, or side-effect sequence
- **AND** the corresponding observation differs
- **THEN** the runtime path alignment report MUST report the
  occurrence-specific mismatch

#### Scenario: Several explicit runs are reviewed
- **WHEN** an exact-path plan contains several current passing runtime runs
- **THEN** FlowGuard MUST review each run independently
- **AND** MUST NOT flatten the end of one run into the beginning of another
