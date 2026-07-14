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

### Requirement: Runtime observations bind business path identity
Runtime path evidence SHALL allow node contracts and observations to bind to an
expected business path id, business intent, and expected terminal when real-code
evidence is used to support a path-sensitive claim.

#### Scenario: Runtime observation proves expected business path
- **WHEN** a runtime observation contains the expected node id and business path identity
- **THEN** the runtime path review records the observation as aligned with that business path

#### Scenario: Runtime observation follows wrong business path
- **WHEN** a runtime observation matches the node id but reports a different business path id, intent, or terminal
- **THEN** the runtime path review reports a mismatch instead of treating the claim as proven

### Requirement: Path-sensitive runtime gaps remain explicit
Runtime path evidence SHALL preserve path-sensitive missing or stale evidence as
review findings rather than silently downgrading the claim.

#### Scenario: Missing business path binding blocks broad claim
- **WHEN** a runtime contract declares a required business path id and the observation omits it
- **THEN** the review reports missing business path binding for that node or path

### Requirement: Runtime evidence preserves fallback masking signals
Runtime path evidence SHALL allow observations and alignment plans to record
primary path id, fallback path id, primary failure id, fallback invocation, and
fallback returned success for path-sensitive claims.

#### Scenario: Runtime fallback masking is reported
- **WHEN** a runtime observation shows the primary path failed, an alternate
  path was invoked because of that failure, and the alternate returned success
- **THEN** the runtime path review SHALL report a silent fallback finding

#### Scenario: No fallback invocation supports evidence
- **WHEN** a path-sensitive runtime observation binds to the expected primary
  path and records that no fallback was invoked
- **THEN** the runtime path review MAY use that observation as no-fallback
  evidence for the declared primary path

### Requirement: Runtime node contracts can name primary authority
Runtime node contracts SHALL be able to declare the primary path id and
expected no-fallback behavior for nodes that support primary-path authority.

#### Scenario: Missing primary path id blocks strict authority proof
- **WHEN** a runtime alignment plan requires primary-path authority evidence
  and a required node contract omits the primary path id
- **THEN** the review SHALL report a missing primary path binding

### Requirement: Runtime path evidence preserves stable behavior authority identity
FlowGuard SHALL carry the stable `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` through required runtime node contracts, runtime observations, and runtime path runs whenever the evidence supports a path-sensitive external behavior claim.

#### Scenario: Runtime observation matches the selected authority
- **WHEN** a required runtime observation names the expected business intent, behavior commitment, and selected primary path
- **THEN** Runtime Path Evidence SHALL retain all three identities in the aligned path result
- **AND** downstream consumers SHALL be able to bind the observation to that exact behavior authority without interpreting free-text intent labels

#### Scenario: Same intent follows a different path
- **WHEN** a runtime observation names the expected `business_intent_id` but a `primary_path_id` different from the selected primary path
- **THEN** Runtime Path Evidence SHALL report a path-authority mismatch
- **AND** the observation SHALL NOT support a current passing path-sensitive claim

#### Scenario: Broad path evidence omits a stable identity
- **WHEN** a done, release, publish, production, archive, or full-confidence runtime path claim omits the stable intent, commitment, or selected primary-path identity
- **THEN** Runtime Path Evidence SHALL keep the missing identity as a blocking gap rather than inferring it from a label, node name, or route name

### Requirement: Runtime path evidence covers the complete declared same-intent surface set
FlowGuard SHALL let a runtime path alignment plan declare the complete expected set of same-intent entry surfaces and Primary Path Authority candidate ids, and SHALL compare that expected set with the materialized runtime contracts and observations before reporting broad confidence.

#### Scenario: Expected surface has no runtime contract
- **WHEN** an expected UI, API, CLI, alias, adapter, wrapper, helper, or facade surface has no runtime node contract or explicit scoped disposition
- **THEN** Runtime Path Evidence SHALL report the expected surface as missing
- **AND** the alignment SHALL NOT treat the caller-selected subset as a complete same-intent inventory

#### Scenario: Expected candidate has no observation or disposition
- **WHEN** a declared Primary Path Authority candidate id has neither current runtime observation evidence nor an explicit non-runtime disposition
- **THEN** Runtime Path Evidence SHALL report the candidate as unaccounted
- **AND** broad no-fallback confidence SHALL remain unavailable

#### Scenario: Complete surface inventory is aligned
- **WHEN** every expected same-intent surface and candidate is represented by a current runtime contract and observation or by an explicit scoped disposition
- **THEN** Runtime Path Evidence MAY report the inventory-completeness portion of alignment as passing
- **AND** it SHALL expose the covered and scoped surface and candidate ids

### Requirement: Retained facade runtime evidence proves delegation to the selected primary path
FlowGuard SHALL treat a retained public facade, alias, adapter, or wrapper as a delegating surface rather than a second runtime authority, and SHALL require current runtime evidence that the surface reaches the selected primary path without owning independent business behavior.

#### Scenario: Facade delegates to the selected primary path
- **WHEN** a retained facade is invoked for a stable business intent
- **AND** the runtime trace shows the facade entering the selected primary path and reaching the primary path terminal
- **THEN** Runtime Path Evidence SHALL record the facade as delegating to that primary path
- **AND** the facade observation MAY support the declared compatibility boundary

#### Scenario: Facade returns success without the selected primary path
- **WHEN** a retained facade or adapter returns business success without an observed delegation to the selected primary path
- **THEN** Runtime Path Evidence SHALL report an alternate-success or delegation mismatch
- **AND** the facade evidence SHALL NOT support primary-path authority confidence

#### Scenario: Facade delegation evidence is stale
- **WHEN** the facade, selected primary path, owner code contract, or runtime binding changes after the delegation observation was produced
- **THEN** Runtime Path Evidence SHALL mark the delegation proof stale
- **AND** current facade compatibility confidence SHALL require a new observation

