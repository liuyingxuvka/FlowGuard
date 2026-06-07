# flowguard-agent-workflow-rehearsal Specification

## Purpose
TBD - created by archiving change add-flowguard-agent-workflow-rehearsal. Update Purpose after archive.
## Requirements
### Requirement: Rehearsal begins with current skill inventory
The system SHALL create a fresh `SkillInventorySnapshot` at the start of every
`flowguard-agent-workflow-rehearsal` invocation.

#### Scenario: Fresh snapshot is required
- **WHEN** an agent invokes `flowguard-agent-workflow-rehearsal`
- **THEN** the rehearsal records a current skill inventory for the
  machine/session before reviewing the workflow plan
- **AND** cached or historical snapshots are not accepted as current evidence

#### Scenario: Candidate skills are deepened selectively
- **WHEN** the fresh snapshot identifies skills that may be relevant to the
  task
- **THEN** the rehearsal may deep-read only those candidate skill bodies
- **AND** unrelated skills can remain represented by lightweight metadata

### Requirement: Agent workflow plans are reviewed before execution
The system SHALL review an `AgentWorkflowPlan` containing selected skills,
skipped candidate skills, ordered steps, side effects, continue gates, rework
gates, validation guidance, and final evidence claims before execution begins.

#### Scenario: Coherent plan passes
- **WHEN** the plan selects relevant skills, orders them safely, defines
  continue and rework gates, maps side effects, and scopes the final evidence
  claim to current validation
- **THEN** the rehearsal result is `pass`

#### Scenario: Missing relevant skill blocks or revises
- **WHEN** the plan skips a relevant candidate skill without a supported reason
- **THEN** the rehearsal result is `blocked` or `needs_revision`
- **AND** the report identifies the skipped skill and consequence

#### Scenario: Wrong order blocks execution
- **WHEN** the plan performs an irreversible or publishing action before its
  required validation and evidence gates
- **THEN** the rehearsal result is `blocked`

### Requirement: Validation guidance weakness stays visible
The system SHALL classify candidate skills' validation guidance as `strong`,
`weak`, `missing`, `manual_only`, or `external_only`, and SHALL keep weak or
missing guidance visible in the rehearsal result.

#### Scenario: Weak validation scopes confidence
- **WHEN** a selected skill is necessary for the plan but has weak or missing
  validation guidance and no compensating smoke, artifact, manual, or dry-run
  check is planned
- **THEN** the rehearsal result is `scoped` or `blocked`
- **AND** the report names the missing validation gate

#### Scenario: Compensating check allows progress
- **WHEN** a selected skill has weak validation guidance but the plan adds a
  concrete compensating check
- **THEN** the rehearsal may allow progress while preserving the scoped evidence
  boundary

### Requirement: Rework and continue gates are explicit
The system SHALL require meaningful non-trivial plans to declare when to
continue and when to rework after validation, skill, side-effect, or evidence
failures.

#### Scenario: Missing rework gate is unsafe
- **WHEN** a plan has staged validation or side effects but does not define a
  rework gate for failed validation
- **THEN** the rehearsal result is `needs_revision` or `blocked`

#### Scenario: Continue gate is evidence-bound
- **WHEN** a plan declares that execution may continue after a step
- **THEN** the continue gate identifies the evidence that supports continuing

### Requirement: Rehearsal is not execution proof
The system SHALL distinguish rehearsal approval from downstream execution,
validation, release, or done evidence.

#### Scenario: Pass does not prove completion
- **WHEN** the rehearsal result is `pass`
- **THEN** the report says the plan may proceed
- **AND** it does not claim the task itself is complete

#### Scenario: Overbroad final claim is downgraded
- **WHEN** the plan claims full done, release, publish, or production confidence
  without matching downstream evidence gates
- **THEN** the rehearsal result is `scoped` or `blocked`

### Requirement: Agent workflow rehearsal accepts plan-detail handoff
AgentWorkflowRehearsal SHALL treat a plan-detail record as the structured workflow handoff for selected skills, skipped candidates, ordered steps, evidence gates, rework gates, and final claim scope.

#### Scenario: Detailed handoff rehearses cleanly
- **WHEN** a plan-detail projection supplies selected skills, ordered steps, continue gates, rework gates, side effects, and final evidence ids
- **THEN** AgentWorkflowRehearsal can review the projected workflow plan

#### Scenario: Missing plan-detail gate remains unsafe
- **WHEN** a projected workflow step lacks required evidence, continue evidence, or rework target
- **THEN** AgentWorkflowRehearsal reports the same gate finding as for a hand-written AgentWorkflowPlan

