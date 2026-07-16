# plan-detailing-compiler Specification

## Purpose
This capability defines FlowGuard's Plan Detailing Compiler behavior and the
evidence required to use it safely when explicitly invoked or delegated by the
development-process simulator in AI-agent maintenance workflows.
## Requirements
### Requirement: PlanDetailing is a delegated development-process simulator mode
FlowGuard SHALL treat PlanDetailing as the `plan_detailing` mode owned by the
development-process simulator front door, while preserving explicit direct
invocation when the user or an existing artifact names this route.

#### Scenario: Generic rough plan enters simulator first
- **WHEN** an agent is asked to discuss, refine, or accept a non-trivial rough
  plan without explicitly naming PlanDetailing
- **THEN** Codex routes first to `flowguard-development-process-flow`
- **AND** the simulator records `plan_detailing` before any delegated
  `flowguard-plan-detailing-compiler` pass

#### Scenario: Explicit PlanDetailing remains valid
- **WHEN** the user or an existing FlowGuard artifact explicitly asks for
  PlanDetailing
- **THEN** `flowguard-plan-detailing-compiler` remains directly invokable

### Requirement: Rough plans are represented as structured detail rows
FlowGuard SHALL provide public data structures for a rough plan's goal, assumptions, scope, source evidence, risk surfaces, artifacts, state surfaces, side effects, ordered steps, receipts, validation requirements, failure branches, rework gates, human-review questions, and final claim boundary.

#### Scenario: Complete plan detail can be serialized
- **WHEN** a plan detail includes goal, scope, artifacts, state surfaces, steps, receipts, validations, failure branches, rework gates, and final evidence
- **THEN** the plan detail can be converted to a dictionary with stable ids for every declared row

#### Scenario: Missing goal is visible
- **WHEN** a plan detail has no goal or task summary
- **THEN** the review report includes a missing-goal finding

### Requirement: Plan detail review blocks under-detailed broad plans
FlowGuard SHALL review a `PlanDetail` and return pass, scoped, needs-revision, or blocked according to missing detail and requested claim scope.

#### Scenario: Happy-path-only plan blocks full claim
- **WHEN** a non-trivial plan has steps and validations but no failure branch or rework gate
- **THEN** the review blocks a full completion claim

#### Scenario: Exploratory plan can remain scoped
- **WHEN** a plan is explicitly exploratory and records missing evidence or human-review questions
- **THEN** the review may return scoped confidence instead of pass

### Requirement: Plan details project to existing FlowGuard routes
FlowGuard SHALL provide helpers that project plan-detail rows into PlanIntake, WorkflowStepContracts, and DevelopmentProcessFlow inputs without replacing those route reviews.

#### Scenario: Plan surfaces project to plan intake
- **WHEN** a plan detail declares source evidence and risk surfaces
- **THEN** the projection produces a `PlanIntakeCompletenessPlan` with matching source and surface ids

#### Scenario: Plan steps project to workflow contracts
- **WHEN** a plan detail declares step receipts and claim gates
- **THEN** the projection produces `WorkflowStepContract` rows that can gate matching claim labels

#### Scenario: Plan lifecycle projects to development process
- **WHEN** a plan detail declares artifacts, actions, validation, evidence, and freshness rules
- **THEN** the projection produces a `DevelopmentProcessPlan` using the same ids

### Requirement: Plan-detail template is executable
FlowGuard SHALL expose a public `plan-detailing-template` CLI that writes an executable starter template and notes.

#### Scenario: Template command writes runnable files
- **WHEN** `python -m flowguard plan-detailing-template --output <dir>` is run
- **THEN** the generated `run_checks.py` exits successfully and prints plan-detail review output

#### Scenario: Template includes broken examples
- **WHEN** the generated plan-detailing template is inspected
- **THEN** it includes broken plan variants for missing validation, missing failure branch, missing rework, and overbroad claim

### Requirement: UI plans name human-operability evidence types
PlanDetailing SHALL require UI tasks that claim human-operable, usable, or
release-ready UI confidence to name evidence types for task coverage,
affordance, action grammar, dialog/window return, keyboard/focus, and
walkthrough validation.

#### Scenario: UI task checkbox has no operability evidence
- **WHEN** a UI plan step is marked complete
- **AND** its claim depends on human-operability
- **THEN** the plan review requires current passing evidence references for the
  relevant human-operability evidence types

### Requirement: UI plans name work mode and source obligations
PlanDetailingCompiler SHALL require UI plans to name UI work mode, source scope when present, target UI scope, allowed differences, evidence types, and must-fail counterexamples before implementation-ready claims.

#### Scenario: Source-based plan lacks source scope
- **WHEN** a UI plan declares source-based or mixed work
- **AND** it lacks source authority, source item/task scope, target mapping obligations, or allowed-difference evidence
- **THEN** plan detailing reports the plan as incomplete

#### Scenario: Greenfield plan has no user task rationale
- **WHEN** a UI plan declares greenfield work
- **AND** it lacks user goals, supported tasks, target UI rationale, or must-fail counterexamples for label-only validation
- **THEN** plan detailing reports the plan as incomplete

### Requirement: Plan discussions route to structured plan detail
PlanDetailing SHALL be the direct FlowGuard route for non-trivial plan discussions,方案 discussions, acceptance-criteria discussions, execution-step discussions, and AI-generated outlines before implementation or broad completion claims begin.

#### Scenario: Non-trivial plan discussion uses plan detailing
- **WHEN** a user and agent discuss a non-trivial implementation plan, validation plan, or acceptance boundary
- **THEN** routing selects `flowguard-plan-detailing-compiler` before downstream FlowGuard execution routes

#### Scenario: Trivial work can skip plan detailing
- **WHEN** the task is a tiny copy edit, direct command answer, formatting-only change, or pure read-only explanation
- **THEN** routing may skip PlanDetailing with a concrete reason

### Requirement: Plan detail preserves subrequirements as execution contracts
PlanDetailing SHALL require non-trivial plans to preserve major items, sub-items, artifacts, validation obligations, failure branches, rework gates, skipped or scoped rows, and final evidence ids as structured rows before the plan can support execution.

#### Scenario: Numbered prose plan is insufficient
- **WHEN** a non-trivial plan contains only a numbered prose outline without stable row ids, validation ids, failure branches, rework gates, or final evidence ids
- **THEN** PlanDetailing blocks or scopes the plan instead of allowing a full execution or done claim

#### Scenario: Subrequirement evidence is preserved
- **WHEN** a plan contains a major item with multiple subrequirements
- **THEN** each subrequirement is represented by a stable step, artifact, validation, evidence, or scoped omission row before full confidence is allowed

### Requirement: Plan detail projections feed execution routes
PlanDetailing SHALL project the same structured rows to WorkflowStepContracts, DevelopmentProcessFlow, and AgentWorkflowRehearsal so downstream routes consume the agreed plan rather than reinterpreting prose.

#### Scenario: Projection keeps ids stable
- **WHEN** PlanDetail rows are projected to downstream routes
- **THEN** step ids, artifact ids, validation ids, evidence ids, and final claim scope remain traceable to the original plan detail

#### Scenario: Missing detail remains visible downstream
- **WHEN** a plan-detail review is scoped or blocked because a row is missing or skipped
- **THEN** downstream route handoff preserves the gap as a claim boundary instead of hiding it behind a fresh prose summary

### Requirement: UI plans name capability coverage evidence
PlanDetailing SHALL require non-trivial UI plans to name functional capability inventory, capability-task mapping, output contracts, implementation bindings, and evidence kinds before execution-ready or done-ready UI claims.

#### Scenario: UI plan names required capabilities
- **WHEN** a UI plan claims user-visible functionality will be implemented or completed
- **THEN** plan detail rows include capability inventory evidence, expected output contracts, implementation binding evidence, and validation or scoped-out boundaries

#### Scenario: UI plan only names controls
- **WHEN** a UI plan lists screens or buttons but omits the required functional capability inventory
- **THEN** the plan is incomplete for broad UI implementation or release claims

### Requirement: UI task rows carry evidence type and status
Plan Detailing Compiler SHALL require UI-related task rows to name completion
evidence type, evidence status, and evidence reference or scoped boundary before
the task can support a done, release, or runnable-UI claim.

#### Scenario: Checked task has no evidence type
- **WHEN** a UI task is marked complete but lacks evidence type and evidence
  status
- **THEN** plan-detail review reports the row as unsupported for UI completion

#### Scenario: Artifact complete is not release complete
- **WHEN** OpenSpec artifacts are complete but UI implementation evidence,
  real-surface inventory, functional-chain evidence, or native/manual signoff
  remains missing
- **THEN** the plan remains artifact-complete only and cannot support release
  confidence

#### Scenario: Evidence type is explicit
- **WHEN** a UI task uses model coverage, static test, runtime click,
  browser DOM/geometry, desktop-shell manual observation, or native-dialog
  blindspot evidence
- **THEN** the task row records that evidence type and whether it is current,
  passing, scoped, stale, planned, or missing

### Requirement: Plans expose UI and payload validation surfaces
PlanDetail SHALL require non-trivial plans to expose UI action, artifact
payload, AI work-package, manual-review, and final-evidence surfaces when those
boundaries can affect the claim.

#### Scenario: Plan includes import/export work
- **WHEN** a plan touches file import, file export, generated artifacts, or AI
  work packages
- **THEN** the plan detail MUST name payload cases, expected evidence kinds,
  failure/rework branches, freshness rules, and final claim boundaries

#### Scenario: Plan includes running UI completion
- **WHEN** a plan claims implemented or runnable UI behavior
- **THEN** the plan detail MUST name the click-through evidence boundary and
  any manual-check or blindspot branches

### Requirement: Plan detail projects strategy execution gates
PlanDetailing SHALL preserve only process-optimization reason ids and required process-optimization evidence ids at the plan boundary. The optimization decision SHALL remain an independently produced evidence artifact consumed through DPF freshness rather than an embedded PlanDetail schema. Detailed steps and validation rows SHALL use their ordinary ordering, required/produced evidence, failure branch, repair action, and validation-requirement fields instead of copying selected policy, campaign, repair-batch, or reevaluation fields into every row.

#### Scenario: Repair group changes governed artifacts
- **WHEN** a plan applies a repair group
- **THEN** ordinary repair actions and validation rows identify its affected revalidation requirements, and DPF freshness blocks completion until current evidence exists

#### Scenario: Ordinary plan does not optimize
- **WHEN** a detailed plan has no process-optimization reason
- **THEN** its projection contains no optimization-evidence references or strategy-specific step/validation fields

### Requirement: PlanDetail preserves provider task identity and mappings
PlanDetail SHALL preserve provider, work-package, change, and task identities plus mapped obligations/checks or typed scoped-out reasons when specification work is projected into plan steps.

#### Scenario: Specification tasks become plan steps
- **WHEN** a provider task list is compiled into PlanDetail rows
- **THEN** every in-scope task SHALL retain its source identity and bidirectional obligation/check mapping through DevelopmentProcessFlow and TestMesh projections

#### Scenario: Task text alone is used as identity
- **WHEN** similar task wording from parallel changes would collapse two tasks
- **THEN** PlanDetail SHALL reject the ambiguous projection

