# development-process-simulator Specification

## Purpose
Define the compact development-process simulator entry that classifies
non-trivial plan discussion, multi-skill workflow setup, staged execution,
validation freshness, install/shadow/git sync, and release/archive/publish
claims into ordered internal modes under `flowguard-development-process-flow`.
## Requirements
### Requirement: Development process simulator is the AI-facing front door
FlowGuard SHALL expose one AI-facing development-process simulator entry for
rough plan discussion, multi-skill/tool workflow rehearsal, staged execution,
validation freshness, install/shadow/git sync, and release/archive/publish
claims.

#### Scenario: Rough plan enters front door
- **WHEN** a non-trivial user request asks to discuss, refine, or make a plan
  detailed before implementation
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `plan_detailing` as an internal mode

#### Scenario: Multi-skill workflow enters front door
- **WHEN** a non-trivial user request requires risk-admitted capability
  sequencing such as an explicit rehearsal request, a cross-owner handoff,
  shared writes, a write that can invalidate post-validation evidence, an
  agent/route workflow change, or multiple independent owners with
  irreversible side effects
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `agent_workflow` as an internal mode

#### Scenario: Low-risk capability surface skips rehearsal
- **WHEN** a task is simple read-only work, has one owner and one tool, and only
  needs targeted checks
- **AND** the request has no explicit rehearsal or risk-admission fact
- **THEN** the simulator SHALL leave `agent_workflow` `not_triggered`
- **AND** it SHALL not create a workflow inventory, rehearsal plan, or receipt

#### Scenario: Capability labels alone do not admit rehearsal
- **WHEN** a request merely names multiple skills, tools, plugins, or an
  external-effect label
- **AND** it has no explicit rehearsal, cross-owner/shared-write,
  post-validation-invalidating-write, route-change, or multi-owner irreversible
  side-effect fact
- **THEN** the simulator SHALL keep `agent_workflow` unselected
- **AND** the owning DevelopmentProcessFlow route and author-side native checks
  SHALL remain authoritative

#### Scenario: Execution freshness enters front door
- **WHEN** a non-trivial user request includes implementation, validation,
  install sync, shadow workspace sync, local git evidence, release, archive, or
  publish confidence
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `execution_freshness` as an internal mode

### Requirement: Simulator preserves internal mode handoffs
The development-process simulator SHALL preserve the ordered handoff from
PlanDetailing rows to AgentWorkflowRehearsal rows to DevelopmentProcessFlow
freshness rows when a task spans more than one mode.

#### Scenario: Plan and execution are linked
- **WHEN** a task starts from a rough plan and later requires staged execution
- **THEN** the simulator SHALL include `plan_detailing` before
  `execution_freshness`
- **AND** the selected modes SHALL preserve the final claim boundary and
  validation evidence gates from the plan-detail rows

#### Scenario: Plan, skills, and release are linked
- **WHEN** a task starts from a rough plan, uses multiple skills, and includes
  release or publish evidence
- **THEN** the simulator SHALL order modes as `plan_detailing`,
  `agent_workflow`, and `execution_freshness`
- **AND** each later mode SHALL consume or cite evidence ids from the earlier
  mode rather than replacing them with prose

### Requirement: Simulator does not replace route evidence
The development-process simulator SHALL classify the mode sequence and handoff
boundary only. It MUST NOT claim that detailed plan review, workflow rehearsal,
or lifecycle freshness evidence has passed unless the owning helper or route
produces current evidence.

#### Scenario: Mode selection is not validation
- **WHEN** the simulator selects `plan_detailing`, `agent_workflow`, or
  `execution_freshness`
- **THEN** the report SHALL say which downstream review remains required
- **AND** it SHALL NOT treat the mode selection itself as completion evidence

#### Scenario: Missing downstream evidence scopes claim
- **WHEN** a final done, release, archive, publish, or full-confidence claim
  lacks current evidence from a selected mode
- **THEN** the simulator SHALL keep the claim scoped or blocked

### Requirement: Retired public satellites resolve to owner-internal modes
FlowGuard SHALL keep PlanDetailing and AgentWorkflowRehearsal behavior only as
internal modes owned by `flowguard-development-process-flow`. Retired public
skill ids, installed directories, aliases, wrappers, and direct invocations
MUST NOT remain successful routes.

#### Scenario: Explicit PlanDetailing request
- **WHEN** a user explicitly asks to use `flowguard-plan-detailing-compiler`
- **THEN** Codex enters `flowguard-development-process-flow` with its internal
  `plan_detailing` mode selected
- **AND** it reports that the named public satellite is retired

#### Scenario: Automatic rough plan does not bypass front door
- **WHEN** a user asks generically to discuss or refine a non-trivial plan
- **THEN** the automatic route SHALL enter `flowguard-development-process-flow`
  first and select only its internal `plan_detailing` mode

### Requirement: Simulator exposes an internal strategy-selection mode
The development process simulator SHALL retain the internal mode id `strategy_selection` and DPF front door, but SHALL select it only when `process_optimization_reasons` includes an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a diagnostic-boundary choice. The request SHALL carry one reason-id collection and one optimization-evidence-id collection instead of separate strategy booleans. Ordinary staged validation or a single obvious route SHALL NOT activate the mode.

#### Scenario: Multiple viable repair sequences
- **WHEN** a staged plan has two outcome-equivalent viable sequences with materially different repeated-work risk
- **THEN** the simulator selects `strategy_selection` and requires current process-optimization evidence before an enforced final claim

#### Scenario: Ordinary implementation has one sequence
- **WHEN** a staged implementation has one clear sequence and no optimization reason
- **THEN** the simulator may select other lifecycle modes but does not select `strategy_selection`

#### Scenario: Material evidence changes an active decision
- **WHEN** an active optimizer's input evidence changes
- **THEN** the simulator preserves the mode identity while DPF requires refreshed decision evidence rather than selecting a separate adaptive mode
