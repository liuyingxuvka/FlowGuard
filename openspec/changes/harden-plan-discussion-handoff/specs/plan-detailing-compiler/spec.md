## ADDED Requirements

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
