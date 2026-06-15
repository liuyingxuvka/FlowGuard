# flowguard-agent-workflow-rehearsal Specification

## Purpose
This capability defines FlowGuard's Flowguard Agent Workflow Rehearsal behavior
and the evidence required to use it safely when explicitly invoked or delegated
by the development-process simulator in AI-agent maintenance workflows.
## Requirements
### Requirement: AgentWorkflowRehearsal is a delegated development-process simulator mode
FlowGuard SHALL treat AgentWorkflowRehearsal as the `agent_workflow` mode owned
by the development-process simulator front door, while preserving explicit
direct invocation when the user or an existing artifact names this route.

#### Scenario: Generic multi-skill work enters simulator first
- **WHEN** an agent is asked to plan non-trivial work involving several skills,
  tools, plugins, external actions, skipped-skill consequences, or side effects
  without explicitly naming AgentWorkflowRehearsal
- **THEN** Codex routes first to `flowguard-development-process-flow`
- **AND** the simulator records `agent_workflow` before any delegated
  `flowguard-agent-workflow-rehearsal` pass

#### Scenario: Explicit rehearsal remains valid
- **WHEN** the user or an existing FlowGuard artifact explicitly asks for
  AgentWorkflowRehearsal
- **THEN** `flowguard-agent-workflow-rehearsal` remains directly invokable

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

### Requirement: Multi-agent UI workflows include human-operability role evidence
AgentWorkflowRehearsal SHALL require a human-operability evidence role for
multi-agent UI workflows that claim complete, usable, or release-ready UI
confidence.

#### Scenario: Human-operability role is missing
- **WHEN** a multi-agent UI workflow claims broad UI confidence
- **AND** role evidence lacks `ui_human_operability`
- **THEN** rehearsal blocks the broad claim or records it as scoped

### Requirement: Multi-agent UI workflows use generic source evidence roles
AgentWorkflowRehearsal SHALL describe UI evidence roles generically as source-baseline inventory, user task flow, target difference review, implementation validation, and integration evidence roles.

#### Scenario: Source-based UI has role evidence
- **WHEN** a multi-agent workflow includes source-based UI scope
- **THEN** rehearsal requires a source-baseline evidence role, a target-difference review role, and an implementation validation role before full runnable UI confidence

#### Scenario: Generic role names avoid source-specific hard gates
- **WHEN** AgentWorkflowRehearsal guidance names UI evidence roles
- **THEN** it does not hard-code one source technology as the generic role name

### Requirement: Agent workflow rehearsal completion ledger
AgentWorkflowRehearsal SHALL include a compact completion ledger in its report
for non-trivial plans.

#### Scenario: Plan is reviewed
- **WHEN** an `AgentWorkflowPlan` is reviewed
- **THEN** the report includes `planned_steps`, `completed_steps`,
  `blocked_steps`, `skipped_steps`, `required_rechecks`, `handoff_points`, and
  `final_claim_boundary`

#### Scenario: A step-level finding blocks execution
- **WHEN** a blocked finding names a workflow step
- **THEN** that step id appears in `blocked_steps`

#### Scenario: Candidate skill is skipped
- **WHEN** a candidate skill is skipped with a disposition row
- **THEN** that skill appears in `skipped_steps`

### Requirement: Rehearsal ledger is not execution proof
The completion ledger SHALL distinguish pre-execution rehearsal from actual
implementation completion evidence.

#### Scenario: Rehearsal passes
- **WHEN** rehearsal status is `pass`
- **THEN** `final_claim_boundary` states that the plan may proceed but downstream
  route evidence is still required for done, release, or publish claims

### Requirement: Rehearsal reports include completion ledger fields
AgentWorkflowRehearsal SHALL expose a completion ledger in its report with planned step ids, completed step ids, blocked step ids, skipped step ids, required recheck ids, handoff evidence ids, and final claim boundary.

#### Scenario: Passing rehearsal reports ledger
- **WHEN** a coherent workflow plan is reviewed
- **THEN** the report includes `planned_steps`, `completed_steps`, `blocked_steps`, `skipped_steps`, `required_rechecks`, `handoff_points`, and `final_claim_boundary`
- **AND** the handoff points include produced, continue, and final evidence ids declared by the plan

#### Scenario: Blocked findings appear in ledger
- **WHEN** a workflow plan has blocking findings for a step or skill
- **THEN** the report lists the affected step or skill in the completion ledger's blocked or required-recheck fields

### Requirement: Rehearsal consumes plan-detail handoff for plan discussions
AgentWorkflowRehearsal SHALL treat a PlanDetail projection as the structured workflow handoff when a non-trivial plan discussion selects multiple skills, tools, agents, side effects, or validation routes.

#### Scenario: Multi-skill plan uses projected steps
- **WHEN** a PlanDetail projection supplies selected skills, ordered steps, evidence gates, side effects, and rework targets
- **THEN** AgentWorkflowRehearsal reviews the projected workflow using those rows rather than a new free-form summary

#### Scenario: Missing projected gate blocks broad claim
- **WHEN** a projected workflow lacks required evidence, continue evidence, final evidence, or a rework target
- **THEN** AgentWorkflowRehearsal reports a finding and the completion ledger prevents full confidence

### Requirement: Completion ledger is not implementation proof
AgentWorkflowRehearsal SHALL identify planned and blocked workflow completion boundaries without claiming that implementation, tests, release, or production validation have completed.

#### Scenario: Ledger does not replace downstream evidence
- **WHEN** a rehearsal report includes completed planned steps and handoff points
- **THEN** the report still requires downstream route evidence before done, release, publish, or production-confidence claims

### Requirement: Multi-agent UI work includes capability coverage role
AgentWorkflowRehearsal SHALL account a UI functional capability inventory and coverage role before full runnable UI confidence when multiple agents collaborate on UI work.

#### Scenario: Multi-agent UI implementation has capability checker
- **WHEN** a multi-agent workflow claims an implemented UI is complete for user-visible functions
- **THEN** the rehearsal evidence includes a role responsible for capability inventory/coverage in addition to visible surface, source-baseline when applicable, user task flow, implementation validation, and integration evidence roles

#### Scenario: Capability role is missing
- **WHEN** UI agents divide design and code work but no role owns required capability inventory, output contracts, and capability-to-evidence binding
- **THEN** AgentWorkflowRehearsal keeps full runnable UI confidence blocked or scoped

### Requirement: UI workflow rehearsal separates evidence roles
AgentWorkflowRehearsal SHALL model non-trivial UI validation work with distinct
evidence roles when multiple agents or workstreams are used: UI inventory,
source-baseline mapping/alignment when relevant, implementation validation,
and main-agent integration.

#### Scenario: UI roles are all present
- **WHEN** a multi-agent UI workflow claims full runnable UI confidence
- **THEN** the rehearsal requires evidence packets for real UI inventory,
  source-baseline mapping/alignment when relevant, implementation click/function-chain
  validation, and integration review

#### Scenario: Agents only edit code
- **WHEN** a multi-agent UI plan assigns all agents to code edits and no agent
  or step owns inventory, semantics, or implementation evidence
- **THEN** rehearsal returns needs-revision or scoped confidence

#### Scenario: Main agent integrates role evidence
- **WHEN** subagents or peer agents produce UI evidence packets
- **THEN** the main agent must consume their evidence ids, current status, and
  blindspots before making a final claim

