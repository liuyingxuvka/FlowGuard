## MODIFIED Requirements

### Requirement: DevelopmentProcessFlow triggers for staged work with validation
FlowGuard SHALL present DevelopmentProcessFlow as the front-door simulator for
any non-trivial plan discussion, multi-skill workflow, staged development, or
modification task where step ordering, touched artifacts, validation evidence,
evidence freshness, peer writes, install/shadow/git sync, release/archive/
publish claims, or minimum revalidation affects whether the agent can safely
continue or claim done.

#### Scenario: Staged implementation trigger
- **WHEN** an agent is asked to complete a non-trivial task with staged actions
  such as plan, edit, test, fix, and verify
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow` during planning
- **AND** the simulator selects `execution_freshness` for artifact and evidence
  freshness

#### Scenario: Plan discussion trigger
- **WHEN** an agent is asked to discuss, expand, or make detailed a
  non-trivial implementation plan
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow`
- **AND** the simulator selects `plan_detailing` and delegates structured row
  review to PlanDetailing

#### Scenario: Multi-skill trigger
- **WHEN** an agent is asked to combine OpenSpec, FlowGuard, plugins, tools,
  external side effects, background checks, install sync, local git evidence,
  or release/publish steps
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow`
- **AND** the simulator selects `agent_workflow` and delegates skill-order
  rehearsal to AgentWorkflowRehearsal

#### Scenario: Not reserved for release readiness
- **WHEN** a task is not yet at release, archive, publish, or final readiness
  but has multiple meaningful development stages and validation
- **THEN** the DevelopmentProcessFlow guidance still treats the route as
  applicable

#### Scenario: Trivial work can skip
- **WHEN** the task is a single-step typo, formatting-only edit, or pure
  explanation with no meaningful validation or artifact freshness risk
- **THEN** the guidance permits skipping DevelopmentProcessFlow with a clear
  reason

### Requirement: DevelopmentProcessFlow is the simulator front door
FlowGuard SHALL keep `flowguard-development-process-flow` as the one
AI-facing development-process simulator skill and SHALL NOT add a separate
fourth Codex skill for development-process simulation.

#### Scenario: Single route wording
- **WHEN** the satellite skill and route documentation are read
- **THEN** they describe `flowguard-development-process-flow` as the single
  simulator front door with internal modes
- **AND** they do not introduce a new sibling skill named as a separate
  development simulator

#### Scenario: Sibling evidence boundary preserved
- **WHEN** DevelopmentProcessFlow references evidence from PlanDetailing,
  AgentWorkflowRehearsal, ModelMesh, TestMesh, StructureMesh, Model-Test
  Alignment, LongCheck, or Conformance Adoption
- **THEN** the guidance continues to say it may use sibling evidence ids and
  freshness metadata but MUST NOT inspect, replace, or supervise sibling route
  internals

### Requirement: DevelopmentProcessFlow consumes simulator mode decisions
DevelopmentProcessFlow SHALL expose a compact mode decision that identifies
which internal reviews are required before broad lifecycle confidence can be
claimed.

#### Scenario: Plan mode requires plan evidence
- **WHEN** the simulator selects `plan_detailing`
- **THEN** the resulting claim boundary SHALL require PlanDetailing evidence
  before the plan can be treated as implementation-ready

#### Scenario: Workflow mode requires rehearsal evidence
- **WHEN** the simulator selects `agent_workflow`
- **THEN** the resulting claim boundary SHALL require AgentWorkflowRehearsal
  evidence before execution, release, archive, publish, or full-confidence
  claims

#### Scenario: Execution mode requires freshness evidence
- **WHEN** the simulator selects `execution_freshness`
- **THEN** the resulting claim boundary SHALL require current
  DevelopmentProcessFlow validation freshness evidence before done, release,
  archive, publish, or full-confidence claims
