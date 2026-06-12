# plan-detailing-compiler Specification

## Purpose
This capability defines FlowGuard's Plan Detailing Compiler behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
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

