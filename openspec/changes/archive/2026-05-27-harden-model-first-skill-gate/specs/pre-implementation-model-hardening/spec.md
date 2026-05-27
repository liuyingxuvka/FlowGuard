## ADDED Requirements

### Requirement: Complex changes use a model-hardening gate
The model-first Skill SHALL require a pre-implementation model-hardening gate
before complex optimization work, repeated bug repairs, stateful refactors,
workflow-sensitive changes, or model-miss-sensitive work proceeds to production
code edits or other high-impact actions.

#### Scenario: Complex optimization before code edits
- **WHEN** an agent is preparing a complex FlowGuard-backed optimization
- **THEN** the Skill requires the agent to complete the model-hardening gate
  before editing production code unless the user explicitly waives modeling

#### Scenario: Trivial work remains lightweight
- **WHEN** a task is clearly trivial, formatting-only, read-only, or has no
  meaningful state or side-effect risk
- **THEN** the Skill allows `skip_with_reason` instead of requiring the gate

### Requirement: Gate records planned changes and risks
The model-hardening gate SHALL require a concrete change inventory and risk
catalog that list planned change slices, affected inputs, state, outputs,
side effects, retries, cache or deduplication paths, likely bugs, and residual
blindspots.

#### Scenario: Agent prepares the gate
- **WHEN** an agent starts the model-hardening gate
- **THEN** the agent records the planned change slices and maps each important
  slice to plausible regressions and affected workflow state

### Requirement: Risks map to executable model coverage
The model-hardening gate SHALL require a risk-to-model coverage matrix that
maps important risks to modeled state, inputs or events, invariants or oracles,
known-bad hazards, check commands or evidence, and residual blindspots.

#### Scenario: Risk has model evidence
- **WHEN** the agent claims a model covers a target regression risk
- **THEN** the coverage matrix names the model element and executable evidence
  that covers that risk

#### Scenario: Risk remains outside model scope
- **WHEN** an important risk cannot reasonably be covered by the model
- **THEN** the coverage matrix marks the risk as a residual blindspot and names
  the production-facing check or human review needed instead

### Requirement: Known-bad hazards validate the model
The model-hardening gate SHALL require known-bad hazards, scenarios, broken
plans, invalid states, or replay cases to fail before the agent trusts a model
as covering the target bug class.

#### Scenario: Known-bad variant is caught
- **WHEN** the model is updated to cover a target risk
- **THEN** at least one representative bad variant for that risk fails or is
  explicitly marked out of scope with rationale

#### Scenario: Green path alone is insufficient
- **WHEN** only a successful plan or happy-path scenario has been checked
- **THEN** the agent cannot claim that the model catches the target bug class

### Requirement: Heavy checks use tiered evidence
The model-hardening gate SHALL require expensive project-specific model groups
to be handled with a tiered evidence policy: run the smallest sufficient model
boundary first, launch long checks in background with declared artifacts when
useful, and record skipped or deferred heavy checks with the reason and residual
risk. The generic Skill MUST NOT hard-code project-specific model names as
always heavy or skippable.

#### Scenario: Heavy model is not on the touched boundary
- **WHEN** an expensive model group does not cover the touched boundary or
  target risk
- **THEN** the agent may skip or defer it while recording the boundary and
  residual risk

#### Scenario: Heavy model covers the touched boundary
- **WHEN** an expensive model group owns the state, contract, or risk being
  changed
- **THEN** the agent cannot silently skip it and must either run it, background
  it with completion evidence, shard it, or report the remaining blocker

### Requirement: Implementation proceeds incrementally after model evidence
The model-first Skill SHALL require agents to implement complex optimized work
in change slices after model evidence passes, validate each slice with the
strongest practical focused checks, preserve peer-agent and user changes, and
rerun or reopen FlowGuard review when runtime validation exposes a model miss.

#### Scenario: Slice validation
- **WHEN** an agent completes an optimization slice
- **THEN** the agent runs the relevant focused model, replay, test, or manual
  validation before continuing to the next slice when practical

#### Scenario: Peer changes are present
- **WHEN** user or peer-agent changes are present in the workspace
- **THEN** the agent preserves those changes and treats stale prior model or
  test evidence as invalid unless the unchanged inputs are explicitly verified
